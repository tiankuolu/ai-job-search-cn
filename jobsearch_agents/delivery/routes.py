from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, HttpUrl, field_validator
import httpx
import pymupdf
from PIL import UnidentifiedImageError

from .service import DeliveryService
from .platforms import Platform
from .imports import JobFields, MAX_UPLOAD_BYTES, save_import
from .filenames import filesystem_path, resume_filename


class SearchRequest(BaseModel):
    platform: Platform = "boss"
    keywords: list[str] = Field(min_length=1, max_length=10)
    limit: int = Field(default=10, ge=1, le=100)
    prepare: bool = True
    include_website_projects: bool = False
    include_english_resume: bool = False
    include_self_description: bool = False


class PrepareRequest(BaseModel):
    job_ids: list[str] = Field(min_length=1, max_length=100)
    revision: str = Field(default="", max_length=4000)
    fresh: bool = False
    include_website_projects: bool = False
    include_english_resume: bool = False
    include_self_description: bool = False
    base_package_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class GreetingRequest(BaseModel):
    greeting: str = Field(min_length=1, max_length=500)


class SendRequest(BaseModel):
    package_ids: list[str] = Field(min_length=1, max_length=100)


class WebsiteProjectsRequest(BaseModel):
    package_ids: list[str] = Field(min_length=1, max_length=1)
    expected_revision: int = Field(ge=0)


class ResumeEditRequest(BaseModel):
    content: str = Field(min_length=1, max_length=200_000)
    base_revision: int = Field(ge=0)


class ResumeExportRequest(BaseModel):
    package_ids: list[str] = Field(min_length=1, max_length=1)
    expected_revision: int = Field(ge=0)


class ManualJobRequest(BaseModel):
    fields: JobFields | None = None
    company: str = Field(default="", max_length=200)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=100_000)
    city: str = Field(default="", max_length=100)
    url: HttpUrl | None = None
    platform: Platform | None = None
    import_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")

    @field_validator("company")
    @classmethod
    def trim_company(cls, value: str) -> str:
        return value.strip()

    @field_validator("title", "description")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("岗位名称和 JD 正文不能为空")
        return "\n".join(value.strip().splitlines())


class URLJobRequest(BaseModel):
    url: HttpUrl


def router(service: DeliveryService):
    routes = APIRouter(prefix="/api/delivery")

    def require_record(table: str, identifier: str):
        try:
            return service.get(table, identifier)
        except KeyError as error:
            raise HTTPException(404, str(error)) from error

    def submit(action: str, data: dict):
        if action != "analyze" and not (service.root / "settings.json").is_file():
            raise HTTPException(503, "本地投递服务尚未配置，请运行 start-integrated.ps1")
        try:
            return service.submit(action, data)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @routes.get("")
    def snapshot():
        return service.snapshot()

    @routes.get("/connection")
    def connection(platform: Platform = "boss"):
        if not (service.root / "settings.json").is_file():
            raise HTTPException(503, "本地投递服务尚未配置")
        try:
            endpoint = "status" if platform == "boss" else f"platforms/{platform}/status"
            return service.bridge().call("GET", endpoint)
        except httpx.HTTPError as error:
            raise HTTPException(502, f"本地投递服务连接失败：{error}") from error

    @routes.post("/login", status_code=202)
    def login(platform: Platform = "boss"):
        return submit("login", {"platform": platform})

    @routes.post("/search", status_code=202)
    def search(body: SearchRequest):
        if any(not keyword.strip() for keyword in body.keywords):
            raise HTTPException(422, "搜索关键词不能为空")
        return submit("search", body.model_dump())

    @routes.post("/imports/extract")
    def extract_job(file: UploadFile = File(...)):
        if Path(file.filename or "").suffix.lower() not in {".md", ".png", ".jpg", ".jpeg", ".webp", ".pdf"}:
            raise HTTPException(415, "支持导入 PDF、Markdown（.md）、PNG、JPEG 和 WebP 文件")
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "文件大小不能超过 20 MB")
        try:
            return save_import(service.root, file.filename or "", data)
        except (ValueError, pymupdf.FileDataError, UnidentifiedImageError) as error:
            raise HTTPException(422, str(error)) from error

    @routes.post("/jobs", status_code=201)
    def add_job(body: ManualJobRequest):
        try:
            return service.add_job(body.model_dump(mode="json"))
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @routes.post("/imports/url")
    def extract_url(body: URLJobRequest):
        try:
            return service.url_importer.read(str(body.url))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except httpx.HTTPError as error:
            raise HTTPException(502, f"招聘网页读取失败：{error}") from error

    @routes.post("/imports/url/open")
    def open_url(body: URLJobRequest):
        try:
            return service.url_importer.open(str(body.url))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except httpx.HTTPError as error:
            raise HTTPException(502, f"招聘网页登录入口无法连接：{error}") from error

    @routes.delete("/jobs/{identifier}")
    def delete_job(identifier: str):
        try:
            return service.delete_job(identifier)
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @routes.post("/analyze", status_code=202)
    def analyze_job(body: PrepareRequest):
        for identifier in body.job_ids:
            require_record("jobs", identifier)
        return submit("analyze", body.model_dump())

    @routes.post("/prepare", status_code=202)
    def prepare(body: PrepareRequest):
        for identifier in body.job_ids:
            require_record("jobs", identifier)
        if body.base_package_id:
            package = require_record("packages", body.base_package_id)
            if body.job_ids != [package["job_id"]] or package["status"] != "ready":
                raise HTTPException(409, "请选择该岗位尚未投递的简历版本进行修改")
        return submit("prepare", body.model_dump())

    @routes.post("/send", status_code=202)
    def send(body: SendRequest):
        if len(set(body.package_ids)) != len(body.package_ids):
            raise HTTPException(422, "投递材料存在重复")
        for identifier in body.package_ids:
            require_record("packages", identifier)
        return submit("deliver", body.model_dump())

    @routes.post("/website-projects", status_code=202)
    def website_projects(body: WebsiteProjectsRequest):
        for identifier in body.package_ids:
            require_record("packages", identifier)
        return submit("website_projects", body.model_dump())

    @routes.post("/supplements/{kind}", status_code=202)
    def supplement(kind: Literal["english_resume", "self_description"], body: WebsiteProjectsRequest):
        for identifier in body.package_ids:
            require_record("packages", identifier)
        return submit(kind, body.model_dump())

    @routes.post("/verify", status_code=202)
    def verify(body: SendRequest):
        for identifier in body.package_ids:
            require_record("packages", identifier)
        return submit("verify", body.model_dump())

    @routes.patch("/packages/{identifier}/greeting")
    def update_greeting(identifier: str, body: GreetingRequest):
        require_record("packages", identifier)
        try:
            return service.update_greeting(identifier, body.greeting)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @routes.get("/packages/{identifier}/resume")
    def resume_editor(identifier: str):
        require_record("packages", identifier)
        try:
            return service.resume_editor(identifier)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @routes.patch("/packages/{identifier}/resume")
    def save_resume(identifier: str, body: ResumeEditRequest):
        require_record("packages", identifier)
        try:
            return service.save_resume(identifier, body.content, body.base_revision)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @routes.post("/packages/{identifier}/resume/convert")
    def convert_resume(identifier: str):
        require_record("packages", identifier)
        try:
            return service.convert_resume(identifier)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @routes.post("/export", status_code=202)
    def export_resume(body: ResumeExportRequest):
        for identifier in body.package_ids:
            require_record("packages", identifier)
        return submit("export", body.model_dump())

    @routes.get("/packages/{identifier}/{kind}")
    def artifact(identifier: str, kind: str):
        media_types = {"pdf": "application/pdf", "image": "image/png", "html": "text/html",
                      "website_projects_file": "text/markdown; charset=utf-8", "self_description_file": "text/markdown; charset=utf-8",
                      "english_html": "text/html", "english_pdf": "application/pdf", "english_image": "image/png"}
        if kind not in media_types:
            raise HTTPException(404, "文件不存在")
        package = require_record("packages", identifier)
        if kind in {"pdf", "image"} and package.get("resume_dirty"):
            raise HTTPException(409, "简历已修改，请重新导出简历后下载")
        if kind == "website_projects_file" and package.get("website_projects_revision") != package.get("editor_revision", 0):
            raise HTTPException(409, "简历已修改，请重新生成官网项目介绍")
        supplement_kind = "english_resume" if kind.startswith("english_") else "self_description" if kind == "self_description_file" else None
        if supplement_kind and package.get(f"{supplement_kind}_revision") != package.get("editor_revision", 0):
            raise HTTPException(409, "简历已修改，请根据当前简历重新生成该材料")
        if kind not in package:
            raise HTTPException(404, "该材料没有此文件")
        path = filesystem_path(Path(package[kind])).resolve(strict=True)
        if not path.is_relative_to((service.root / "packages").resolve()):
            raise HTTPException(403, "文件路径无效")
        filename = ("官网投递项目介绍.md" if kind == "website_projects_file" else "自我描述.md" if kind == "self_description_file"
                    else resume_filename(package.get("company"), package["title"] + ("-EN" if kind.startswith("english_") else ""), path.suffix))
        return FileResponse(path, media_type=media_types[kind], headers={"Cache-Control": "no-store"}, filename=filename,
                            content_disposition_type="attachment" if kind.endswith("_file") or kind == "english_html" else "inline")

    return routes

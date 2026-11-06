from typing import Literal


Platform = Literal["boss", "liepin", "nowcoder", "shixiseng"]
PLATFORM_NAMES = {"boss": "BOSS", "liepin": "猎聘", "nowcoder": "牛客", "shixiseng": "实习僧"}


def submission_confirmed(package: dict, receipt: dict) -> bool:
    if package.get("platform", "boss") == "boss":
        return receipt.get("greeting_sent") is True and receipt.get("image_sent") is True
    if receipt.get("submission_type") == "greeting_image":
        return (receipt.get("submitted") is True and receipt.get("greeting_sent") is True
                and receipt.get("image_sent") is True and receipt.get("image_sha256") == package["image_sha256"])
    return receipt.get("submitted") is True and receipt.get("resume_sha256") == package["pdf_sha256"]

(() => {
  const sheet = document.querySelector('main.sheet');
  let readOnly = resumeEditorConfig.readOnly;
  const send = (type, data = {}) => parent.postMessage({type, packageId: resumeEditorConfig.packageId, ...data}, '*');
  const reportHeight = () => send('resume.height', {height: Math.max(1123, Math.ceil(sheet.getBoundingClientRect().height))});
  const setMode = value => {
    readOnly = value;
    sheet.contentEditable = String(!readOnly);
  };
  setMode(readOnly);
  sheet.setAttribute('aria-label', '简历正文');
  sheet.setAttribute('role', 'textbox');
  sheet.setAttribute('aria-multiline', 'true');
  sheet.addEventListener('input', () => {
    if (!readOnly) send('resume.changed', {content: sheet.innerHTML});
    reportHeight();
  });
  sheet.addEventListener('paste', event => {
    if (readOnly) return;
    event.preventDefault();
    document.execCommand('insertText', false, event.clipboardData.getData('text/plain'));
  });
  sheet.addEventListener('click', event => {
    if (event.target.closest('a')) event.preventDefault();
  });
  window.addEventListener('message', event => {
    if (event.source !== parent || event.data?.packageId !== resumeEditorConfig.packageId) return;
    if (event.data.type === 'resume.mode') setMode(event.data.readOnly);
    if (event.data.type === 'resume.snapshot') send('resume.snapshot', {requestId: event.data.requestId, content: sheet.innerHTML});
    if (event.data.type === 'resume.format' && !readOnly) {
      if (['bold', 'italic', 'underline', 'undo', 'redo'].includes(event.data.command)) document.execCommand(event.data.command);
    }
  });
  new ResizeObserver(reportHeight).observe(sheet);
  document.fonts.ready.then(reportHeight);
  send('resume.ready', {revision: resumeEditorConfig.revision, content: sheet.innerHTML});
})();

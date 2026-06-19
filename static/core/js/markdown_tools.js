(function () {
    const copiedText = '已复制'
    const copyText = '复制'

    function getCsrfToken() {
        const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]')
        if (csrfInput) {
            return csrfInput.value
        }
        const cookie = document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))
        return cookie ? decodeURIComponent(cookie.split('=')[1]) : ''
    }

    function copyToClipboard(text) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(text)
        }
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.setAttribute('readonly', 'readonly')
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
        return Promise.resolve()
    }

    function enhanceCodeBlocks(root) {
        const scope = root || document
        scope.querySelectorAll('.sr-markdown-body pre').forEach((pre) => {
            if (pre.dataset.srCopyReady === 'true') {
                return
            }
            pre.dataset.srCopyReady = 'true'
            const wrapper = document.createElement('div')
            wrapper.className = 'sr-code-wrap'
            pre.parentNode.insertBefore(wrapper, pre)
            wrapper.appendChild(pre)

            const button = document.createElement('button')
            button.type = 'button'
            button.className = 'sr-code-copy'
            button.textContent = copyText
            button.addEventListener('click', () => {
                copyToClipboard(pre.innerText).then(() => {
                    button.textContent = copiedText
                    window.setTimeout(() => {
                        button.textContent = copyText
                    }, 1200)
                })
            })
            wrapper.appendChild(button)
        })
    }

    function typesetMath(root) {
        if (!window.MathJax || !window.MathJax.typesetPromise) {
            return
        }
        window.MathJax.typesetPromise(root ? [root] : undefined)
    }

    function postPreview(endpoint, markdown) {
        const body = new FormData()
        body.append('markdown', markdown)
        return fetch(endpoint, {
            body,
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': getCsrfToken(),
            },
            method: 'POST',
        }).then((response) => response.json())
    }

    function syncPreview(textarea, preview, endpoint) {
        if (!textarea || !preview || !endpoint) {
            return Promise.resolve()
        }
        preview.dataset.srRendering = 'true'
        return postPreview(endpoint, textarea.value).then((data) => {
            preview.innerHTML = data.html || ''
            preview.dataset.srRendering = 'false'
            enhanceCodeBlocks(preview)
            typesetMath(preview)
        })
    }

    function bindEditor(options) {
        const root = options.root || document
        const query = (target) => (typeof target === 'string' ? root.querySelector(target) : target)
        const queryAll = (target) => (typeof target === 'string' ? Array.from(root.querySelectorAll(target)) : Array.from(target || []))
        const textarea = query(options.textarea)
        const preview = query(options.preview)
        const codePanel = query(options.codePanel)
        const visualPanel = query(options.visualPanel)
        const tabs = queryAll(options.tabs)
        const endpoint = options.endpoint
        let timer = null
        let renderVersion = 0

        if (!textarea || !preview || !codePanel || !visualPanel || !tabs.length) {
            return
        }

        function renderPreview() {
            const currentVersion = renderVersion + 1
            renderVersion = currentVersion
            preview.dataset.srRendering = 'true'
            return postPreview(endpoint, textarea.value).then((data) => {
                if (currentVersion !== renderVersion) {
                    return
                }
                preview.innerHTML = data.html || ''
                preview.dataset.srRendering = 'false'
                enhanceCodeBlocks(preview)
                typesetMath(preview)
            }).catch(() => {
                if (currentVersion === renderVersion) {
                    preview.dataset.srRendering = 'false'
                }
            })
        }

        function queuePreview(delay) {
            window.clearTimeout(timer)
            timer = window.setTimeout(() => {
                renderPreview()
            }, delay ?? 120)
        }

        function setMode(mode) {
            const visualMode = mode === 'visual'
            if (!visualMode && document.activeElement === preview) {
                textarea.value = preview.innerText.trim()
            }
            codePanel.hidden = visualMode
            visualPanel.hidden = !visualMode
            tabs.forEach((tab) => {
                const active = tab.dataset.mode === mode
                tab.setAttribute('aria-pressed', String(active))
            })
            if (visualMode) {
                renderPreview()
            }
        }

        tabs.forEach((tab) => {
            tab.addEventListener('click', () => setMode(tab.dataset.mode))
        })
        textarea.addEventListener('input', () => queuePreview())
        preview.addEventListener('input', () => {
            if (preview.dataset.srRendering !== 'true') {
                textarea.value = preview.innerText.trimEnd()
                queuePreview(220)
            }
        })
        enhanceCodeBlocks(preview)
        typesetMath(preview)
        setMode(options.initialMode || 'code')
    }

    function bindAdminEditor(options) {
        const textarea = document.querySelector(options.textarea || '#id_markdown')
        if (!textarea || textarea.dataset.srAdminReady === 'true') {
            return
        }
        textarea.dataset.srAdminReady = 'true'

        const shell = document.createElement('div')
        shell.className = 'sr-admin-markdown-editor'

        const controls = document.createElement('div')
        controls.className = 'sr-admin-editor-controls'
        controls.innerHTML = [
            '<button type="button" class="sr-editor-tab" data-mode="visual" aria-pressed="false">所见即所得</button>',
            '<button type="button" class="sr-editor-tab" data-mode="code" aria-pressed="true">代码模式</button>',
        ].join('')

        const codePanel = document.createElement('div')
        codePanel.className = 'sr-editor-panel sr-admin-code-panel'
        textarea.parentNode.insertBefore(shell, textarea)
        shell.appendChild(controls)
        shell.appendChild(codePanel)
        codePanel.appendChild(textarea)

        const visualPanel = document.createElement('div')
        visualPanel.className = 'sr-editor-panel sr-admin-visual-panel'
        visualPanel.hidden = true

        const preview = document.createElement('div')
        preview.className = 'sr-markdown-shell sr-markdown-body sr-visual-editor sr-admin-preview'
        preview.contentEditable = 'true'
        visualPanel.appendChild(preview)
        shell.appendChild(visualPanel)

        bindEditor({
            codePanel: '.sr-admin-code-panel',
            endpoint: options.endpoint,
            initialMode: 'code',
            preview: '.sr-admin-preview',
            root: shell,
            tabs: '.sr-admin-editor-controls .sr-editor-tab',
            textarea: '#id_markdown',
            visualPanel: '.sr-admin-visual-panel',
        })
    }

    document.addEventListener('DOMContentLoaded', () => {
        enhanceCodeBlocks(document)
        typesetMath(document.body)
    })

    window.SRMarkdown = {
        bindAdminEditor,
        bindEditor,
        enhanceCodeBlocks,
        syncPreview,
        typesetMath,
    }
}())

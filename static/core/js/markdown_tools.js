(function () {
    const copiedText = '已复制'
    const copyText = '复制'

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

    function normalizePreviewRoot(root) {
        if (!root) {
            return null
        }
        if (root.jquery) {
            return root[0] || null
        }
        return root
    }

    function prepareMarkdownBody(root) {
        const scope = normalizePreviewRoot(root) || document
        if (scope.classList && scope.classList.contains('martor-preview')) {
            scope.classList.add('sr-markdown-shell', 'sr-markdown-body')
        }
        scope.querySelectorAll('.martor-preview').forEach((preview) => {
            preview.classList.add('sr-markdown-shell', 'sr-markdown-body')
        })
        enhanceCodeBlocks(scope)
        typesetMath(scope)
    }

    function bindMartorPreviewEvents() {
        if (document.documentElement.dataset.srMartorPreviewReady === 'true') {
            return true
        }
        const jq = window.jQuery || (window.django && window.django.jQuery)
        if (!jq) {
            return false
        }
        document.documentElement.dataset.srMartorPreviewReady = 'true'
        jq(document).on('martor:preview', (event, preview) => {
            prepareMarkdownBody(preview)
        })
        return true
    }

    document.addEventListener('DOMContentLoaded', () => {
        prepareMarkdownBody(document)
        if (!bindMartorPreviewEvents()) {
            window.setTimeout(bindMartorPreviewEvents, 300)
        }
    })

    window.SRMarkdown = {
        enhanceCodeBlocks,
        prepareMarkdownBody,
        typesetMath,
    }
}())

(function () {
  var STORAGE_KEY = "ymicore_token";
  var RETRIED_KEY = "ymicore_retried";
  var isLogin = document.body.classList.contains("login-body");

  // Session persistence: the admin token is saved in localStorage so the
  // session survives cookie expiry and works across domains/incognito flows.
  if (isLogin) {
    var loginForm = document.querySelector('form[action="/auth/token"]');
    var input = loginForm && loginForm.querySelector('input[name="token"]');

    if (loginForm) {
      loginForm.addEventListener("submit", function () {
        if (input && input.value) localStorage.setItem(STORAGE_KEY, input.value);
      });

      // A failed attempt means the remembered token was rejected, forget it
      // so we don't retry a revoked token forever.
      if (document.querySelector("[role=alert]")) {
        localStorage.removeItem(STORAGE_KEY);
        sessionStorage.removeItem(RETRIED_KEY);
      }

      // Silently restore a remembered token, once per tab session.
      var stored = localStorage.getItem(STORAGE_KEY);
      if (stored && input && !input.value && !sessionStorage.getItem(RETRIED_KEY)) {
        sessionStorage.setItem(RETRIED_KEY, "1");
        input.value = stored;
        loginForm.submit();
      }
    }
  } else {
    // We're authenticated on this page; allow the next silent restore.
    sessionStorage.removeItem(RETRIED_KEY);
  }

  // Logging out must also forget the remembered token.
  var logoutForm = document.querySelector('form[action="/auth/logout"]');
  if (logoutForm) {
    logoutForm.addEventListener("submit", function () {
      localStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(RETRIED_KEY);
    });
  }

  // Copy freshly minted tokens to the clipboard.
  var copyBtn = document.getElementById("copy-token");
  var tokenEl = document.getElementById("new-token");
  if (copyBtn && tokenEl) {
    copyBtn.addEventListener("click", function () {
      var text = tokenEl.textContent.trim();
      var done = function () {
        copyBtn.textContent = "Copied";
        setTimeout(function () { copyBtn.textContent = "Copy"; }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, done);
      } else {
        var ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); } catch (e) {}
        document.body.removeChild(ta);
        done();
      }
    });
  }

  // Success toast: fade out after a moment.
  var toast = document.getElementById("saved-toast");
  if (toast) {
    var parent = toast.parentElement;
    setTimeout(function () {
      toast.classList.add("lecp-toast--leaving");
    }, 2600);
    setTimeout(function () {
      if (parent && parent.parentElement) parent.parentElement.removeChild(parent);
    }, 2900);
  }

  // Confirm destructive actions.
  document.querySelectorAll("[data-confirm]").forEach(function (button) {
    button.addEventListener("click", function (event) {
      if (!window.confirm(button.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });

  // Show a loading spinner state on submit while the request is in flight.
  document.querySelectorAll("form[data-submitting]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var button = form.querySelector('button[type="submit"]');
      if (button && !button.dataset.pressed) {
        button.dataset.pressed = "1";
        button.classList.add("lecp-btn--loading");
        button.setAttribute("aria-busy", "true");
      }
    });
  });

  // Live Markdown preview for note editors.
  (function () {
    var bodyInput = document.getElementById("body");
    var preview = document.getElementById("markdown-preview");
    if (!bodyInput || !preview) return;
    function escapeHtml(s) {
      var d = document.createElement("span");
      d.textContent = s;
      return d.innerHTML;
    }
    function renderMarkdown(s) {
      var o = escapeHtml(s);
      o = o.replace(/```(\w*)\n?([\s\S]*?)```/g, "<pre><code>$2</code></pre>")
           .replace(/`([^`]+)`/g, "<code>$1</code>")
           .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
           .replace(/\*([^\s*][^*]*)\*/g, "<em>$1</em>")
           .replace(/_([^\s_][^_]*?)_/g, "<em>$1</em>")
           .replace(/~~(.+?)~~/g, "<s>$1</s>")
           .replace(/\|\|(.+?)\|\|/g, "<s style='opacity:0.6'>$1</s>")
           .replace(/\[([^\]]+)\]\((\S+)\)/g, "<a href='$2'>$1</a>")
           .replace(/(?:^|\n)(#{1,6})\s+(.+)/g, "$1<strong>$2</strong>")
           .replace(/\n/g, "<br>");
      return o;
    }
    var update = function () {
      preview.innerHTML = renderMarkdown(bodyInput.value || "");
    };
    bodyInput.addEventListener("input", update);
    update();
  })();
})();
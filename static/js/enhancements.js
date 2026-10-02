/* ==========================================================================
   Optional progressive enhancements (vanilla JS).

   Everything in this file is a *nice to have*. Each feature is guarded by its
   own try/catch and starts with an early return when its prerequisite is
   missing, so a failure here can never break the server-rendered page.

   Features
   1. Report whether the enhancement layer is actually active.
   2. Confirm destructive actions (still a plain POST form when JS is absent).
   3. Keyboard focus management after an HTMX swap.
   4. Drag & drop of issue cards between board columns (bonus interactivity).
   ========================================================================== */

(function () {
  "use strict";

  var config = window.ISSUE_TRACKER || {};

  function onReady(fn) {
    if (document.readyState !== "loading") {
      fn();
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  }

  /* -- 1. enhancement status pill ---------------------------------------- */
  function reportEnhancementStatus() {
    var pill = document.getElementById("js-status");
    if (!pill) return;
    var active = typeof window.htmx !== "undefined";
    pill.innerHTML = "JS <strong>" + (active ? "enhanced" : "basic") + "</strong>";
    pill.title = active
      ? "HTMX is active: actions update small HTML fragments without a page reload."
      : "JavaScript is unavailable: the server-rendered HTML is fully functional.";
    pill.classList.toggle("pill--enhanced", active);
  }

  /* -- 2. destructive action confirmation --------------------------------- */
  function installConfirmations() {
    document.addEventListener("click", function (event) {
      var trigger = event.target.closest("[data-confirm]");
      if (!trigger) return;
      var message = trigger.getAttribute("data-confirm");
      if (!window.confirm(message)) {
        event.preventDefault();
        event.stopPropagation();
      }
    });
  }

  /* -- 3. focus management after a swap ----------------------------------- */
  function manageFocusAfterSwap() {
    document.body.addEventListener("htmx:afterSwap", function (event) {
      var target = event.detail && event.detail.target;
      if (!target || typeof target.focus !== "function") return;
      // Move focus into the freshly swapped content so keyboard and screen
      // reader users are not stranded at the top of the document.
      if (!target.hasAttribute("tabindex")) {
        target.setAttribute("tabindex", "-1");
      }
      target.focus({ preventScroll: true });
      target.addEventListener(
        "blur",
        function handler() {
          target.removeAttribute("tabindex");
          target.removeEventListener("blur", handler);
        },
        { once: true }
      );
    });
  }

  /* -- 4. drag & drop between board columns ------------------------------- */
  function columnStatus(columnBody) {
    return columnBody ? columnBody.getAttribute("data-status") : null;
  }

  function installDragAndDrop() {
    var board = document.querySelector(".board");
    if (!board || typeof window.DragEvent === "undefined") return;

    var dragged = null;

    board.addEventListener("dragstart", function (event) {
      var card = event.target.closest(".issue-card");
      if (!card) return;
      dragged = card;
      card.classList.add("is-dragging");
      // htmx serialises the dragged element into the request body when the
      // drop target is a form; here the drop is handled manually instead.
      if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
    });

    board.addEventListener("dragend", function () {
      if (dragged) dragged.classList.remove("is-dragging");
      dragged = null;
    });

    board.addEventListener("dragover", function (event) {
      var column = event.target.closest(".board__column-body");
      if (!column || !dragged) return;
      event.preventDefault();
      column.classList.add("is-drop-target");
    });

    board.addEventListener("dragleave", function (event) {
      var column = event.target.closest(".board__column-body");
      if (column) column.classList.remove("is-drop-target");
    });

    board.addEventListener("drop", function (event) {
      var column = event.target.closest(".board__column-body");
      if (!column || !dragged) return;
      event.preventDefault();
      column.classList.remove("is-drop-target");

      var targetStatus = columnStatus(column);
      var card = dragged;
      dragged = null;
      if (!targetStatus || card.getAttribute("data-status") === targetStatus) return;

      var url = "/issues/" + card.getAttribute("data-issue-id") + "/update-status/";
      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-CSRFToken": config.csrfToken || "",
          // Send the HTMX header so the server replies with a fragment; a plain
          // form POST from a browser without JS still gets the 302 redirect.
          "HX-Request": "true"
        },
        body: "status=" + encodeURIComponent(targetStatus)
      })
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.text();
        })
        .then(function (html) {
          column.insertAdjacentHTML("beforeend", html);
          var oldColumn = card.parentNode;
          if (oldColumn) oldColumn.removeChild(card);
          updateCounts(board);
        })
        .catch(function (error) {
          if (config.debug) console.error("Drag & drop update failed", error);
        });
    });
  }

  function updateCounts(board) {
    board.querySelectorAll(".board__column-body").forEach(function (body) {
      var slug = body.getAttribute("data-status-slug") ||
        (body.getAttribute("data-status") || "").toLowerCase().replace(/ /g, "-");
      var counter = board.querySelector('[data-count-for="' + slug + '"]');
      if (counter) {
        counter.textContent = String(body.querySelectorAll(".issue-card").length);
      }
    });
  }

  onReady(function () {
    try { reportEnhancementStatus(); } catch (e) { if (config.debug) console.error(e); }
    try { installConfirmations(); } catch (e) { if (config.debug) console.error(e); }
    try { manageFocusAfterSwap(); } catch (e) { if (config.debug) console.error(e); }
    try { installDragAndDrop(); } catch (e) { if (config.debug) console.error(e); }
  });
})();
/*
 * The forum structure tree's drag and drop and move buttons (todo 668).
 *
 * Plain script, no build step, no inline code (the production CSP has no
 * 'unsafe-inline'): configuration arrives in data-* attributes on
 * #wf-structure. Uses the pinned SortableJS in ./vendor/ (Wagtail's bundled
 * copy is not a public API). Every move is one POST of
 * {forum_id, parent_id, position} to data-move-url; the server checks the
 * rules and renumbers, and a refused move snaps back with its message.
 */
(function () {
  "use strict";

  var root = document.getElementById("wf-structure");
  if (!root || root.dataset.canChange !== "true") {
    return;
  }
  var moveUrl = root.dataset.moveUrl;
  var csrfInput = root.querySelector("input[name=csrfmiddlewaretoken]");
  var csrf = csrfInput ? csrfInput.value : "";
  var status = document.getElementById("wf-structure-status");
  var sortables = [];
  var busy = false;

  function say(message, isError) {
    status.textContent = message || "";
    status.classList.toggle("wf-structure__status--error", Boolean(isError));
  }

  function setBusy(value) {
    busy = value;
    root.classList.toggle("wf-structure--busy", value);
    sortables.forEach(function (sortable) {
      sortable.option("disabled", value);
    });
  }

  function send(forumId, parentId, position) {
    var body = new FormData();
    body.append("forum_id", forumId);
    body.append("parent_id", parentId || "");
    body.append("position", String(position));
    setBusy(true);
    say(root.dataset.msgSaving);
    return fetch(moveUrl, {
      method: "POST",
      body: body,
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (response) {
        return response
          .json()
          .catch(function () {
            return {};
          })
          .then(function (data) {
            if (!response.ok) {
              throw new Error(data.message || root.dataset.msgFailed);
            }
            return data;
          });
      })
      .finally(function () {
        setBusy(false);
      });
  }

  function itemsOf(list) {
    return Array.prototype.filter.call(list.children, function (child) {
      return child.hasAttribute("data-forum-id");
    });
  }

  function ownForm(item, kind) {
    // The row's own move form, never one of a nested forum row.
    var row = item.querySelector(":scope > .wf-structure__row");
    return row ? row.querySelector('form[data-move="' + kind + '"]') : null;
  }

  /* Bring every row's buttons and no-JavaScript fallback values in line
   * with the DOM after a move. */
  function refresh() {
    var lists = root.querySelectorAll(
      ".wf-structure__categories, .wf-structure__forums",
    );
    Array.prototype.forEach.call(lists, function (list) {
      var items = itemsOf(list);
      items.forEach(function (item, index) {
        var up = ownForm(item, "up");
        var down = ownForm(item, "down");
        var to = ownForm(item, "to");
        [up, down].forEach(function (form) {
          if (form) {
            form.elements.parent_id.value = list.dataset.parentId;
          }
        });
        if (up) {
          up.elements.position.value = String(Math.max(index - 1, 0));
          up.querySelector("button").disabled = index === 0;
        }
        if (down) {
          down.elements.position.value = String(index + 1);
          down.querySelector("button").disabled = index === items.length - 1;
        }
        if (to) {
          var select = to.elements.parent_id;
          Array.prototype.forEach.call(select.options, function (option) {
            option.disabled = option.value === list.dataset.parentId;
          });
          var current = select.options[select.selectedIndex];
          if (!current || current.disabled) {
            var free = Array.prototype.find.call(select.options, function (o) {
              return !o.disabled;
            });
            if (free) {
              select.value = free.value;
            }
          }
        }
      });
    });
  }

  function applyResult(item, data) {
    var badge = item.querySelector(
      ":scope > .wf-structure__row [data-hidden-badge]",
    );
    if (badge && typeof data.is_hidden === "boolean") {
      badge.hidden = !data.is_hidden;
    }
    say(data.message);
  }

  /* Put a dragged row back where it came from. */
  function revert(evt) {
    evt.item.parentNode.removeChild(evt.item);
    evt.from.insertBefore(evt.item, itemsOf(evt.from)[evt.oldIndex] || null);
  }

  function onEnd(evt) {
    if (evt.from === evt.to && evt.oldIndex === evt.newIndex) {
      return;
    }
    send(evt.item.dataset.forumId, evt.to.dataset.parentId, evt.newIndex)
      .then(function (data) {
        applyResult(evt.item, data);
      })
      .catch(function (error) {
        revert(evt);
        say(error.message, true);
      })
      .finally(refresh);
  }

  function makeSortable(list, group, handle, draggable) {
    sortables.push(
      window.Sortable.create(list, {
        group: group,
        handle: handle,
        draggable: draggable,
        animation: 150,
        fallbackOnBody: true,
        swapThreshold: 0.65,
        emptyInsertThreshold: 24,
        onEnd: onEnd,
      }),
    );
  }

  if (window.Sortable) {
    var categories = root.querySelector(".wf-structure__categories");
    if (categories) {
      makeSortable(
        categories,
        "wf-categories",
        ".wf-structure__handle--category",
        ".wf-structure__category",
      );
    }
    Array.prototype.forEach.call(
      root.querySelectorAll(".wf-structure__forums"),
      function (list) {
        makeSortable(
          list,
          "wf-forums",
          ".wf-structure__handle--forum",
          ".wf-structure__forum",
        );
      },
    );
  }

  // Line the controls up with the DOM before the first move.
  refresh();

  /* The move buttons: same endpoint, the row moves in place and the
   * keyboard focus stays on the control that was used. */
  root.addEventListener("submit", function (evt) {
    var form = evt.target.closest("form.wf-structure__move");
    if (!form) {
      return;
    }
    evt.preventDefault();
    if (busy) {
      return;
    }
    var item = form.closest("[data-forum-id]");
    var list = item.parentElement;
    var items = itemsOf(list);
    var index = items.indexOf(item);
    var kind = form.dataset.move;
    var targetList = list;
    var position;
    if (kind === "up") {
      position = index - 1;
    } else if (kind === "down") {
      position = index + 1;
    } else {
      targetList = root.querySelector(
        '.wf-structure__forums[data-parent-id="' +
          form.elements.parent_id.value +
          '"]',
      );
      if (!targetList) {
        return;
      }
      position = itemsOf(targetList).length;
    }
    if (position < 0 || (kind === "down" && position >= items.length)) {
      return;
    }
    var control = document.activeElement;
    send(item.dataset.forumId, targetList.dataset.parentId, position)
      .then(function (data) {
        var siblings = itemsOf(targetList).filter(function (other) {
          return other !== item;
        });
        targetList.insertBefore(item, siblings[position] || null);
        applyResult(item, data);
      })
      .catch(function (error) {
        say(error.message, true);
      })
      .finally(function () {
        refresh();
        var focusTarget = control && item.contains(control) ? control : null;
        if (focusTarget && focusTarget.disabled) {
          // Moved to the top or bottom: the other arrow is still there.
          var other = ownForm(item, kind === "up" ? "down" : "up");
          focusTarget = other ? other.querySelector("button") : null;
        }
        if (focusTarget) {
          focusTarget.focus();
        }
      });
  });
})();

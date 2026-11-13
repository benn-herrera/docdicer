"use strict";

// The board page. Everything shown comes from the server's payload (GET /api/board); every action
// is a POST whose effect reaches the page through the same long poll, so the page holds no state of
// its own beyond the version it last drew, the drag under way and whether the server answers.

const log = (level, message, context = {}) => console[level]({ level, message, ...context });

const DRAG_TYPE = "application/x-docdicer-card";
const ROADMAP = "roadmap";
const DESIGN = "design";

const $ = (id) => document.getElementById(id);
const boardEl = $("board");

let dragging = null; // {kind: "roadmap" | "parked" | "design", card} while a drag runs
let deferred = null; // a payload that arrived during the drag, shown when it ends
let drawn = null; // the version of the payload on the page; null after a failed poll
let stopped = false; // the server has not answered STOPPED_AFTER polls in a row: no drag starts
let ended = false; // the server was stopped from the page: polling has ended for good
const dragInfo = new WeakMap(); // card element -> its drag info
const separatorCard = new WeakMap(); // Roadmap category separator element -> its card as served

const STOPPED_AFTER = 3;
const STOPPED_TEXT = "server stopped: restart docdicer kanban and open the URL it prints";
const NOT_DRAWN = "board not drawn: ";
const PARKED_BAND = "ROADMAP_DESIGNS";

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

const columnLabel = (column) => column[0].toUpperCase() + column.slice(1);

// A code span, a markdown link whose text is shown in its place, strong (**x**) or emphasis (*x*);
// the leftmost match wins, so nothing inside a code span is touched, and at one position strong is
// tried before emphasis. Delimited text may not start or end in whitespace. Underscores are never
// markup. Groups: 1-2 code, 3 link, 4 strong, 5 em.
const INLINE = new RegExp(
  [
    "(`+)(.+?)\\1(?!`)",
    "\\[([^\\]]*)\\]\\([^)]*\\)",
    "\\*\\*(?=\\S)(.+?)(?<=\\S)\\*\\*",
    "\\*(?=\\S)(.+?)(?<=\\S)\\*",
  ].join("|"),
  "g",
);

// Append text to parent with its code spans as <code>, links as their text, and strong and emphasis
// as <strong> and <em>, whose contents are rendered in turn. Only text nodes and those elements are
// created: file text never reaches the page as markup.
function appendInline(parent, text) {
  let at = 0;
  for (const match of text.matchAll(INLINE)) {
    parent.append(text.slice(at, match.index));
    const [, ticks, code, link, strong, em] = match;
    if (ticks) parent.append(el("code", "", code));
    else if (link !== undefined) appendInline(parent, link);
    else {
      const child = el(strong !== undefined ? "strong" : "em");
      appendInline(child, strong ?? em);
      parent.append(child);
    }
    at = match.index + match[0].length;
  }
  parent.append(text.slice(at));
}

function inlineEl(className, text, tag = "div") {
  const e = el(tag, className);
  appendInline(e, text);
  return e;
}

// A link to a file the server serves, opening in a new tab. It does not drag itself, so a drag
// started on it drags the card holding it.
function linkEl(href) {
  const a = el("a");
  a.href = href;
  a.target = "_blank";
  a.rel = "noopener";
  a.draggable = false;
  return a;
}

// A card's title, a link to href where there is one.
function titleEl(text, href) {
  if (!href) return inlineEl("title", text);
  const e = el("div", "title");
  const a = linkEl(href);
  appendInline(a, text);
  e.append(a);
  return e;
}

// ---- rendering ---------------------------------------------------------------------------------

// Draw payload unless it is the version already drawn: a long poll that times out answers the
// same version, and redrawing it would only reset what the user scrolled.
function render(payload) {
  if (dragging) {
    deferred = payload; // replacing the dragged element mid-drag would cancel the drag
    return;
  }
  if (payload.version === drawn) return;
  try {
    const { board } = payload;
    $("release").textContent = board.release ? `Release ${board.release}` : "";
    $("hardening").hidden = !board.hardening;
    const title = `${payload.project} kanban`;
    document.title = title;
    $("page-title").textContent = title;
    $("connection").title = `docdicer v${payload.docdicer_version}`;
    renderColumns(payload);
    drawn = payload.version;
    if ($("alert").textContent.startsWith(NOT_DRAWN)) showAlert("");
  } catch (error) {
    showAlert(NOT_DRAWN + String(error.message || error));
    log("error", "board not drawn", { version: payload.version, error: String(error) });
  }
}

function renderColumns({ board, plan_columns }) {
  const scrolled = new Map();
  for (const section of boardEl.querySelectorAll(".column")) {
    scrolled.set(section.dataset.column, section.querySelector(".cards").scrollTop);
  }
  const keys = [ROADMAP, DESIGN, ...plan_columns];
  const lists = new Map();
  const sections = keys.map((key) => {
    const section = el("section", plan_columns.includes(key) ? "column plan" : "column");
    section.dataset.column = key;
    const head = el("div", "column-head");
    head.append(el("h2", "", columnLabel(key)));
    const list = el("div", "cards");
    section.append(head, list);
    lists.set(key, list);
    return section;
  });

  for (const notice of board.notices) lists.get(notice.column).append(noticeEl(notice));
  for (const card of board.roadmap) lists.get(ROADMAP).append(roadmapCard(card));
  if (board.parked.length) lists.get(ROADMAP).append(separatorEl({ title: PARKED_BAND }));
  for (const card of board.parked) lists.get(ROADMAP).append(parkedCard(card, { kind: "parked", card }));
  for (const card of board.design) lists.get(DESIGN).append(designCard(card));
  for (const pkg of board.packages) lists.get(pkg.state).append(packageCard(pkg));
  boardEl.replaceChildren(...sections);
  for (const [key, list] of lists) list.scrollTop = scrolled.get(key) ?? 0;
}

function draggable(element, info) {
  element.draggable = true;
  dragInfo.set(element, info);
  return element;
}

// A category or a delta: a separator band, a heading below the column's, not a card.
const separatorEl = (card) => inlineEl("separator", card.title, "h3");

// Content outside the layout, shown at the head of the column it names: where it is, the text
// found as written (an empty one as `found an empty line`, as check-roadmap and check-design say it)
// and the form accepted there.
function noticeEl(notice) {
  const e = el("div", "layout-notice");
  const found = el("div", "", notice.found ? "found: " : "found an empty line");
  if (notice.found) found.append(el("code", "", notice.found));
  e.append(el("div", "meta", `${notice.path}:${notice.line}`), found, inlineEl("", `accepted: ${notice.accepted}`));
  return e;
}

// A roadmap part: a category's separator, or a ticket's card titled over its text, which drags.
function roadmapCard(card) {
  if (card.kind !== "ticket") {
    const separator = separatorEl(card);
    separatorCard.set(separator, card);
    return separator;
  }
  const e = el("div", "card");
  e.append(titleEl(card.title, card.href));
  if (card.text) e.append(textEl(card.text));
  if (card.parked && card.parked.length) {
    const list = el("ul", "parked");
    list.append(...card.parked.map((path) => el("li", "", path)));
    e.append(list);
  }
  return draggable(e, { kind: "roadmap", card });
}

// A piece of parked work: its title, a link to its heading where it is a link ticket's (href), and a
// link to each of its files, paths[k] to hrefs[k].
function parkedCard({ title, paths, hrefs, href }, info) {
  const e = el("div", "card");
  e.append(el("div", "group", "parked"), titleEl(title, href));
  for (const [k, path] of paths.entries()) {
    const a = linkEl(hrefs[k]);
    a.textContent = path;
    const meta = el("div", "meta");
    meta.append(a);
    e.append(meta);
  }
  return draggable(e, info);
}

// A ticket's text as markdown paragraphs: blank lines separate them, a paragraph's lines join with
// one space.
function textEl(text) {
  const e = el("div", "text");
  for (const block of text.split(/\n[ \t]*\n/)) {
    const line = block.split("\n").map((l) => l.trim()).filter(Boolean).join(" ");
    if (!line) continue;
    const para = el("div", "para");
    appendInline(para, line);
    e.append(para);
  }
  return e;
}

// A design part. A category or a delta is a separator; a delta's entry is a flat card that does not
// drag. A ticket's card: a link ticket looks like its parked work's parked card, any other is
// titled over the ticket's text; either drags as the design card served.
function designCard(card) {
  if (card.kind === "category" || card.kind === "delta") return separatorEl(card);
  const info = { kind: "design", card };
  if (card.parked !== null) {
    return parkedCard({ title: card.title, paths: card.parked, hrefs: card.parked_hrefs, href: card.href }, info);
  }
  const e = el("div", card.kind === "entry" ? "card entry" : "card");
  e.append(titleEl(card.title, card.href));
  if (card.text) e.append(textEl(card.text));
  return card.kind === "ticket" ? draggable(e, info) : e;
}

// A work package's card; not draggable, its state changing only by an edit to the plan.
function packageCard(pkg) {
  const e = el("div", "card");
  e.append(titleEl(`${pkg.id} ${pkg.title || "untitled"}`, pkg.href));
  const meta = [pkg.rating ?? "unrated"];
  if (pkg.lifetime) meta.push(`Lifetime: ${pkg.lifetime}`);
  e.append(el("div", "meta", meta.join(" · ")));
  return e;
}

// ---- actions -----------------------------------------------------------------------------------

// #move-message (role="status") carries the move message, #alert (role="alert") failures.
const showMoveMessage = (text) => ($("move-message").textContent = text);
const showAlert = (text) => ($("alert").textContent = text);

// POST an action; its effect on the board arrives through the long poll. Resolves to the response
// body, or to null where the action failed, the failure shown naming its cause. Only a 409 is a
// refusal that wrote nothing; a 500 names any files the move had already written.
async function act(path, body) {
  showMoveMessage("");
  showAlert("");
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const answer = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
    if (response.ok) return answer;
    const refused = response.status === 409 ? "Not moved: " : "";
    const written = answer.written && answer.written.length ? ` (already written: ${listed(answer.written)})` : "";
    showAlert(refused + answer.error + written);
    log("warn", "action failed", { path, body, status: response.status, error: answer.error });
  } catch (error) {
    showAlert(String(error.message || error));
    log("warn", "action failed", { path, body, error: String(error) });
  }
  return null;
}

// "a", "a and b", "a, b and c"
const listed = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`);

// ---- drag and drop -----------------------------------------------------------------------------

// The only drops accepted: a roadmap or parked card on Design, a design ticket's card on Roadmap.
// Elsewhere dragover is left uncancelled, so the browser refuses the drop and the card returns.
function accepts(info, column) {
  if (column === DESIGN) return info.kind === "roadmap" || info.kind === "parked";
  return column === ROADMAP && info.kind === "design";
}

// The element under the pointer, a text node's parent for the text node.
const targetElement = (event) => (event.target instanceof Element ? event.target : event.target.parentElement);

// The column under the pointer.
function dropColumn(event) {
  const node = targetElement(event);
  const section = node && node.closest(".column");
  return section ? section.dataset.column : null;
}

// The Roadmap category separator nearest above the pointer, as served: the band dropped on, else
// the last band whose top is above the card or gap dropped on; null where none is, or where the drop
// lands on the column's head band, which stays in place while the cards scroll beneath it. The
// ROADMAP_DESIGNS band is no category's and is passed over.
function separatorAbove(event) {
  const node = targetElement(event);
  if (node && node.closest(".column-head")) return null;
  let found = null;
  for (const band of boardEl.querySelectorAll(`.column[data-column="${ROADMAP}"] .separator`)) {
    if (band.getBoundingClientRect().top > event.clientY) break;
    if (separatorCard.has(band)) found = separatorCard.get(band);
  }
  return found;
}

boardEl.addEventListener("dragstart", (event) => {
  // A drag may start on an element inside the card, such as its title's link.
  const card = targetElement(event)?.closest(".card");
  const info = card ? dragInfo.get(card) : undefined;
  if (!info) return;
  if (stopped) {
    event.preventDefault();
    return;
  }
  dragging = info;
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData(DRAG_TYPE, info.card.id ?? info.card.title); // Firefox starts no drag without data
});

boardEl.addEventListener("dragend", () => {
  dragging = null;
  if (deferred) {
    const payload = deferred;
    deferred = null;
    render(payload);
  }
});

boardEl.addEventListener("dragover", (event) => {
  const column = dropColumn(event);
  if (!dragging || !column || !accepts(dragging, column)) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
});

// A move between Roadmap and Design; the move message names the files it wrote, in write order.
function moveTicket(path, body, destination) {
  act(path, body).then((answer) => {
    if (answer) showMoveMessage(`Moved "${body.card.title}" to ${destination}: wrote ${listed(answer.written)}.`);
  });
}

boardEl.addEventListener("drop", (event) => {
  const column = dropColumn(event);
  if (!dragging || !column || !accepts(dragging, column)) return;
  event.preventDefault();
  const { card } = dragging;
  if (column === DESIGN) {
    moveTicket("/api/to-design", { card }, "Design");
  } else {
    // The ticket joins the category whose separator is nearest above the drop; with none, the first.
    moveTicket("/api/to-roadmap", { card, target: separatorAbove(event) }, "Roadmap");
  }
});

// Anything dragged in that is not a card, such as a file, is refused everywhere, so that the
// browser's default drop does not replace the page with it.
for (const type of ["dragover", "drop"]) {
  document.addEventListener(type, (event) => {
    if (dragging) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "none";
  });
}

// ---- live following ----------------------------------------------------------------------------

function showConnection(text) {
  const connection = $("connection");
  if (connection.textContent !== text) connection.textContent = text; // an unchanged text is not re-announced
}

// Each answer carries a version; asking with it waits until the board changes. After a failure the
// next ask carries no version, and the version drawn is forgotten, since a restarted server counts
// versions from 1 again.
// Polling ends for good once the server is stopped from the page (`ended`): an answer or a failure
// arriving after that, such as the waiting poll the closing server answers, changes nothing.
async function follow() {
  let since = null;
  let delay = 500;
  let failures = 0;
  while (!ended) {
    let payload;
    try {
      const response = await fetch(since === null ? "/api/board" : `/api/board?since=${since}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      payload = await response.json();
    } catch (error) {
      if (ended) return;
      if (failures === 0) log("warn", "board connection lost", { error: String(error) });
      failures += 1;
      since = null;
      drawn = null;
      stopped = failures >= STOPPED_AFTER;
      showConnection(stopped ? STOPPED_TEXT : "reconnecting…");
      await new Promise((resolve) => setTimeout(resolve, delay * (0.5 + Math.random())));
      delay = Math.min(delay * 2, 8000);
      continue;
    }
    if (ended) return;
    since = payload.version;
    delay = 500;
    failures = 0;
    stopped = false;
    showConnection("live");
    render(payload);
  }
}

// Stop the server, with no confirmation. The button is disabled while the POST runs, so a second
// press cannot reach a server already closing; its answer first moves focus, which the disabled
// button drops, to the page heading, then sets the stopped state for good, so that the focus change
// does not cut off the indicator's live-region announcement. A failed POST shows as any failed
// action does, re-enables the button, and polling goes on.
$("stop").addEventListener("click", async () => {
  $("stop").disabled = true;
  if (!(await act("/api/stop", {}))) {
    $("stop").disabled = false;
    return;
  }
  $("page-title").focus();
  ended = true;
  stopped = true;
  showConnection(STOPPED_TEXT);
});

follow();

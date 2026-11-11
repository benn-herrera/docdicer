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
const dragInfo = new WeakMap(); // card element -> its drag info

const STOPPED_AFTER = 3;
const NOT_DRAWN = "board not drawn: ";

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

function inlineEl(className, text) {
  const e = el("div", className);
  appendInline(e, text);
  return e;
}

const titleEl = (text) => inlineEl("title", text);

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

  for (const card of board.roadmap) lists.get(ROADMAP).append(roadmapCard(card));
  for (const card of board.parked) lists.get(ROADMAP).append(parkedCard(card));
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

function roadmapCard(card) {
  const e = el("div", "card");
  if (card.group) e.append(el("div", "group", card.group));
  e.append(titleEl(card.title));
  if (card.parked && card.parked.length) {
    const list = el("ul", "parked");
    list.append(...card.parked.map((path) => el("li", "", path)));
    e.append(list);
  }
  return draggable(e, { kind: "roadmap", card });
}

function parkedCard(card, info = { kind: "parked", card }) {
  const e = el("div", "card");
  e.append(el("div", "group", "parked"), titleEl(card.title), el("div", "meta", card.path));
  return draggable(e, info);
}

// A section's text as markdown paragraphs: blank lines separate them, a paragraph's lines join with
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

// A design section's card: a parked entry's link section looks like that parked card, any other
// is titled by its heading over the section's text. Either drags as the design card served.
function designCard(card) {
  const info = { kind: "design", card };
  if (card.parked !== null) return parkedCard({ title: card.title, path: card.parked }, info);
  const e = el("div", "card");
  e.append(titleEl(card.title));
  if (card.text) e.append(textEl(card.text));
  return draggable(e, info);
}

// A work package's card; not draggable, its state changing only by an edit to the plan.
function packageCard(pkg) {
  const e = el("div", "card");
  e.append(titleEl(`${pkg.id} ${pkg.title || "untitled"}`));
  const meta = [pkg.rating ?? "unrated"];
  if (pkg.lifetime) meta.push(`Lifetime: ${pkg.lifetime}`);
  e.append(el("div", "meta", meta.join(" · ")));
  return e;
}

// ---- actions -----------------------------------------------------------------------------------

// #notice (role="status") carries successes, #alert (role="alert") failures.
const showNotice = (text) => ($("notice").textContent = text);
const showAlert = (text) => ($("alert").textContent = text);

// POST an action; its effect on the board arrives through the long poll. Resolves to the response
// body, or to null where the action failed, the failure shown naming its cause. Only a 409 is a
// refusal that wrote nothing; a 500 names any files the move had already written.
async function act(path, body) {
  showNotice("");
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

// The only drops accepted: a roadmap or parked card on Design, a design card on Roadmap. Elsewhere
// dragover is left uncancelled, so the browser refuses the drop and the card returns.
function accepts(info, column) {
  if (column === DESIGN) return info.kind === "roadmap" || info.kind === "parked";
  return column === ROADMAP && info.kind === "design";
}

// The column under the pointer, and the drag info of the card under it, if any.
function dropTarget(event) {
  const node = event.target instanceof Element ? event.target : event.target.parentElement;
  const section = node && node.closest(".column");
  const card = node && node.closest(".card");
  return { column: section ? section.dataset.column : null, over: card ? dragInfo.get(card) : undefined };
}

boardEl.addEventListener("dragstart", (event) => {
  const info = event.target instanceof Element ? dragInfo.get(event.target) : undefined;
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
  const { column } = dropTarget(event);
  if (!dragging || !column || !accepts(dragging, column)) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
});

// A move between Roadmap and Design; the notice names the files it wrote, in write order.
function moveEntry(path, body, destination) {
  act(path, body).then((answer) => {
    if (answer) showNotice(`Moved "${body.card.title}" to ${destination}: wrote ${listed(answer.written)}.`);
  });
}

boardEl.addEventListener("drop", (event) => {
  const { column, over } = dropTarget(event);
  if (!dragging || !column || !accepts(dragging, column)) return;
  event.preventDefault();
  const { card } = dragging;
  if (column === DESIGN) {
    moveEntry("/api/to-design", { card }, "Design");
  } else {
    // Dropped on a roadmap or parked card, the item joins that card's group; elsewhere, the file's end.
    moveEntry("/api/to-roadmap", { card, target: over ? over.card : null }, "Roadmap");
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
async function follow() {
  let since = null;
  let delay = 500;
  let failures = 0;
  for (;;) {
    let payload;
    try {
      const response = await fetch(since === null ? "/api/board" : `/api/board?since=${since}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      payload = await response.json();
    } catch (error) {
      if (failures === 0) log("warn", "board connection lost", { error: String(error) });
      failures += 1;
      since = null;
      drawn = null;
      stopped = failures >= STOPPED_AFTER;
      showConnection(stopped ? "server stopped: restart docdicer kanban and open the URL it prints" : "reconnecting…");
      await new Promise((resolve) => setTimeout(resolve, delay * (0.5 + Math.random())));
      delay = Math.min(delay * 2, 8000);
      continue;
    }
    since = payload.version;
    delay = 500;
    failures = 0;
    stopped = false;
    showConnection("live");
    render(payload);
  }
}

follow();

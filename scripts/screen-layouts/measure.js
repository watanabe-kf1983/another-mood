// Reports the laid-out geometry of a screen mockup so that
// `chrome --dump-dom` can hand it to generate_layouts.py.  The result is
// appended as a JSON script element rather than logged, because --dump-dom
// gives us the DOM and nothing else.
//
// The mockups carry no marks for this script: a part's shape follows from its
// tag, and every run of text is measured wherever the browser put it.  That is
// what lets the mockups stay plain HTML that a reader can open and edit.

const SHAPES = {
  MAIN: {},                    // the screen frame
  H1: { shaded: true },        // the screen-name band
  INPUT: {},                   // an io item — shaded when readonly, i.e. output
  SELECT: { marker: true },    // an io item chosen from registered values
  BUTTON: { shaded: true },    // an action
  TH: { shaded: true },
  TD: {},
};

addEventListener("load", () => {
  const root = document.querySelector("main");
  const origin = root.getBoundingClientRect();

  const round = (n) => Math.round(n * 10) / 10;
  const place = (box) => ({
    x: round(box.x - origin.x),
    y: round(box.y - origin.y),
    w: round(box.width),
    h: round(box.height),
  });

  const rects = [...root.querySelectorAll(Object.keys(SHAPES).join(","))].map((el) => {
    const shape = SHAPES[el.tagName];
    return {
      kind: "rect",
      ...place(el.getBoundingClientRect()),
      shaded: Boolean(shape.shaded) || el.hasAttribute("readonly"),
      marker: Boolean(shape.marker),
      radius: parseFloat(getComputedStyle(el).borderTopLeftRadius) || 0,
    };
  });
  // The frame itself is the origin, and querySelectorAll skips the root.
  rects.unshift({
    kind: "rect",
    ...place(origin),
    shaded: false,
    marker: false,
    radius: 0,
  });

  const texts = [];
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walk.nextNode(); node; node = walk.nextNode()) {
    const raw = node.textContent;
    const text = raw.trim();
    if (!text) continue;
    // Measure the glyphs, not the text node: the indentation of the source
    // would otherwise be read as part of the run.
    const range = document.createRange();
    range.setStart(node, raw.length - raw.trimStart().length);
    range.setEnd(node, raw.trimEnd().length);
    const style = getComputedStyle(node.parentElement);
    texts.push({
      kind: "text",
      text,
      ...place(range.getBoundingClientRect()),
      fontSize: parseFloat(style.fontSize),
      bold: Number(style.fontWeight) >= 600,
    });
  }

  const payload = {
    title: document.title,
    width: round(origin.width),
    height: round(origin.height),
    parts: [...rects, ...texts],
  };

  const out = document.createElement("script");
  out.type = "application/json";
  out.id = "wf-measured";
  out.textContent = JSON.stringify(payload);
  document.body.appendChild(out);
});

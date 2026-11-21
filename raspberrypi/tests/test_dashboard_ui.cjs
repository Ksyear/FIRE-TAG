const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function page(search = '') {
  const nodes = new Map();
  function element() {
    return {textContent: '', innerHTML: '', className: '', value: '0', checked: true,
      disabled: false, dataset: {}, children: [], listeners: {}, style: {setProperty() {}},
      setAttribute(k, v) {this[k] = v;}, appendChild(n) {this.children.push(n);},
      removeAttribute(k) {delete this[k];},
      addEventListener(name, callback) {this.listeners[name] = callback;},
      querySelectorAll(selector) {return this.children.filter(n => selector === 'button' || n.className.split(' ').includes(selector.slice(1)));}, remove() {},
      getBoundingClientRect() {return {width: 1000, height: 700};}};
  }
  const document = {getElementById(id) {if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id);},
    createElement: element, createElementNS: element, body: element()};
  document.getElementById('csvLink').href = '/api/positions.csv?minutes=60';
  const fetchCalls = [];
  const context = vm.createContext({document, AbortController, console, URLSearchParams, location: {search},
    fetch: (...args) => {fetchCalls.push(args); return new Promise(() => {});}, setTimeout() {return 1;}, clearTimeout() {}});
  const html = fs.readFileSync(path.join(__dirname, '../web/index_full.html'), 'utf8');
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
  return {context, nodes, fetchCalls, run: code => vm.runInContext(code, context)};
}

function state() {
  return {db: true, auto_calibrate: false, calibration: null,
    anchors: [0, 1, 2].map(id => ({id, online: true, x: id, y: id % 2, age_s: .1})),
    tags: [{id: 0, x: 1, y: 2, lost: true, age_s: 20, rms: .1,
      ranges: {'0': 2, '1': 3, '2': 4}, uwb_ranges: {
        '0': {fresh: true, range_m: 2, age_s: .1}, '1': {fresh: true, range_m: 3, age_s: .1},
        '2': {fresh: false, range_m: 4, age_s: 20}}, trail: []}], events: [], commands: []};
}

test('a heartbeat from A2 cannot turn missing UWB measurements into live tracking', () => {
  const p = page(); p.context.state = state();
  assert.equal(p.run('typeof renderSummary'), 'function');
  p.run('renderSummary(state)');
  assert.equal(p.nodes.get('systemBanner').dataset.state, 'range_missing');
  assert.match(p.nodes.get('statusDetail').textContent, /A2/);
});

test('a calibration in progress cannot be presented as live tracking', () => {
  const p = page(); p.context.state = {...state(), auto_calibrate: true};
  assert.equal(p.run('typeof renderSummary'), 'function');
  p.run('renderSummary(state)');
  assert.equal(p.nodes.get('systemBanner').dataset.state, 'calibrating');
});

test('a solved-range residual is not labelled as guaranteed plus/minus accuracy', () => {
  const p = page(); p.context.state = state(); p.run('renderTags(state)');
  assert.doesNotMatch(p.nodes.get('tagInfo').innerHTML, /±/);
  assert.match(p.nodes.get('tagInfo').innerHTML, /마지막 위치/);
});

test('a failed API request immediately invalidates the tracking banner and controls', () => {
  const p = page(); p.run('setLink(false, "Pi 연결 끊김")');
  assert.equal(p.nodes.get('systemBanner')?.dataset.state, 'offline');
  assert.equal(p.nodes.get('alertBtn').disabled, true);
});

test('choosing a cached Tag after disconnect cannot reactivate live state or commands', () => {
  const p = page(); const s = state(); s.tags[0].lost = false;
  p.context.state = s;
  p.run('setLink(false, "Pi 연결 끊김"); renderSummary(state); renderTags(state); renderControls(state)');
  assert.equal(p.nodes.get('systemBanner').dataset.state, 'offline');
  assert.equal(p.nodes.get('alertBtn').disabled, true);
  assert.match(p.nodes.get('tagInfo').innerHTML, /마지막 위치/);
});

test('horizontal reversal mirrors both Tag and anchors while keeping text readable', () => {
  const p = page(); const s = state(); s.tags[0].lost = false;
  s.tags[0].x = 1; s.tags[0].y = 2;
  s.tags[0].trail = [[[1, 2], [2, 3]]];
  s.anchors = [{id: 0, x: 0, y: 0, online: true}, {id: 1, x: 3, y: 0, online: true}, {id: 2, x: 0, y: 4, online: true}];
  p.context.state = s;
  assert.equal(p.run('typeof mapX'), 'function');
  p.run('horizontalFlipped = true; buildStatic(state); drawDynamic(state)');
  const all = [];
  function walk(node) {all.push(node); for (const child of node.children) walk(child);}
  walk(p.nodes.get('map'));
  assert.equal(all.find(n => n.class === 'tag-g').style.transform, 'translate(-1px, -2px)');
  assert.ok(all.some(n => n.transform === 'translate(-3 0)' && n.children.some(c => c.textContent === 'A1')));
  assert.ok(all.some(n => n.d === 'M-1 -2L-2 -3'));
  assert.ok(all.some(n => n.cx === -3 && n.cy === 0 && n.r === 3));
  assert.ok(all.some(n => n.textContent === 3 && n.x < -2));
  assert.equal(all.some(n => String(n.transform).includes('scale(-1')), false);
});

test('the virtual building has multiple selectable floors and distinct simulated Tags', () => {
  const p = page('?demo=1');
  assert.equal(p.run('typeof demoState'), 'function');
  const a = p.run('demoState("F1", 0)'); const b = p.run('demoState("F2", 0)');
  assert.equal(a.simulated, true); assert.equal(b.floor.id, 'F2');
  assert.ok(a.tags.length >= 2 && b.tags.length >= 2);
  assert.ok(a.floorplan.length > 0);
  assert.ok(a.tags.every(t => !b.tags.some(u => u.id === t.id)));
  assert.notEqual(a.tags[0].x, p.run('demoState("F1", 2).tags[0].x'));
});

test('simulation mode cannot send commands to physical devices', async () => {
  const p = page('?demo=1');
  p.nodes.get('zoneSelect').listeners.change({target: {value: 'Z4'}});
  p.context.fetch = () => {throw new Error('physical API must not be called');};
  await assert.rejects(p.run('post("/api/command", {cmd:"reboot",target:2})'), /가상/);
  await assert.rejects(p.run('post("/api/alert", {tag:0,on:true})'), /가상/);
  assert.equal(p.fetchCalls.length, 0);
  assert.equal(p.nodes.get('csvLink').href, undefined);
  assert.equal(p.nodes.get('alertBtn').disabled, true);
  assert.equal(p.nodes.get('pingBtn').disabled, true);
  assert.ok(p.nodes.get('cmdButtons').children.every(b => b.disabled));
});

test('changing the virtual floor redraws its plan and chooses a Tag on that floor', () => {
  const p = page('?demo=1');
  p.nodes.get('zoneSelect').listeners.change({target: {value: 'Z4'}});
  p.nodes.get('floorSelect').listeners.change({target: {value: 'F2'}});
  assert.equal(p.run('latestState.floor.id'), 'F2');
  assert.equal(p.run('latestState.zone?.id'), 'Z1');
  assert.equal(p.nodes.get('zoneSelect')?.value, 'Z1');
  assert.equal(p.run('latestState.tags.some(t => t.id === selectedTag)'), true);
  assert.match(p.nodes.get('statusTitle').textContent, /가상/);
  assert.match(p.nodes.get('tagInfo').innerHTML, /가상/);
  assert.equal(p.fetchCalls.length, 0);
});

test('each room plan confines three noncollinear candidate anchors and virtual Tags to that room', () => {
  const p = page('?demo=1');
  for (const floor of ['F1', 'F2']) {
    const plan = p.run(`demoState("${floor}", 0)`);
    assert.ok(plan.zone, 'the default room must be selected');
    for (const room of plan.floorplan) {
      for (const t of [-100, 0, 20, 10000]) {
        const s = p.run(`demoState("${floor}", ${t}, "${room.id}")`);
        assert.equal(s.zone.id, room.id);
        assert.equal(s.anchors.length, 3);
        assert.equal(s.tags.length, 3);
        const inside = ({x, y}) => x > room.x0 && x < room.x1 && y > room.y0 && y < room.y1;
        assert.ok(s.anchors.every(inside));
        assert.ok(s.tags.every(inside));
        assert.ok(s.tags.every(tag => tag.trail.flat().every(([x, y]) => inside({x, y}))));
        const [a, b, c] = s.anchors;
        assert.ok(Math.abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)) > .01);
        assert.ok(s.anchors.every(a => a.online !== true));
      }
    }
  }
});

test('choosing another room changes the installation plan without touching physical devices', () => {
  const p = page('?demo=1');
  const before = p.run('latestState.anchors[0].y');
  assert.equal(typeof p.nodes.get('zoneSelect')?.listeners.change, 'function');
  p.nodes.get('zoneSelect').listeners.change({target: {value: 'Z4'}});
  assert.equal(p.run('latestState.zone.name'), '복도');
  assert.notEqual(p.run('latestState.anchors[0].y'), before);
  assert.match(p.nodes.get('statusDetail').textContent, /벽 너머.*미검증/);
  assert.match(p.nodes.get('anchorList').innerHTML, /설치 후보/);
  assert.doesNotMatch(p.nodes.get('anchorList').innerHTML, /dot ok/);
  assert.equal(p.run('[...layers.anchorEls.values()].every(e => e.style.fill === "var(--amber)")'), true);
  assert.equal(p.run('layers.ranges["clip-path"]'), 'url(#demo-zone-clip)');
  const boundary = p.run('layers.grid.children.find(e => e.class === "zone-selected")');
  assert.equal(boundary.x, 0);
  assert.equal(boundary.y, -7);
  assert.equal(boundary.width, 18);
  assert.equal(boundary.height, 2);
  assert.equal(p.fetchCalls.length, 0);
});

test('recordings retain simulation and disconnected labels', () => {
  const live = page(); live.context.state = state();
  assert.match(live.run('recordingLabel(state)'), /실측/);
  live.run('apiConnected = false');
  assert.match(live.run('recordingLabel(state)'), /연결 끊김/);
  const demo = page('?demo=1'); demo.context.state = state();
  assert.match(demo.run('recordingLabel(state)'), /시뮬레이션/);
  assert.match(demo.run('recordingLabel(latestState)'), /교실 101/);
});

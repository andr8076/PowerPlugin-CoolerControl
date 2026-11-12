const test = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {JSDOM, VirtualConsole} = require('jsdom');

const html = readFileSync(join(__dirname, '..', 'ui', 'index.html'), 'utf8');
const SENSOR = 'temp5d2f065aff73';

function harness(initial = {}, shouldPersist = true, additionalSensors = []) {
    let config = JSON.parse(JSON.stringify(initial));
    const errors = [];
    const virtualConsole = new VirtualConsole();
    virtualConsole.on('jsdomError', error => errors.push(error.message));
    const dom = new JSDOM(html, {
        runScripts: 'dangerously',
        url: 'http://localhost/',
        virtualConsole,
        beforeParse(window) {
            window.runPluginScript = callback => void callback();
            window.getDevices = async () => [{
                name: 'Power to Temperature',
                uid: 'test-device',
                info: {
                    temps: new window.Map([
                        [SENSOR, {label: 'amdgpu PPT (power %)'}],
                        ...additionalSensors,
                    ])
                }
            }];
            window.getPluginConfig = async () => JSON.parse(JSON.stringify(config));
            window.savePluginConfig = async values => {
                if (shouldPersist) {
                    config = JSON.parse(JSON.stringify(values));
                }
            };
            window.getStatus = async () => new window.Map([
                ['test-device', new window.Map([[SENSOR, {temp: '40.0'}]])]
            ]);
        }
    });
    return {dom, errors, getConfig: () => config};
}

const flush = () => new Promise(resolve => setTimeout(resolve, 75));

test('wattage is saved on field change, confirmed and persisted in the UI', async () => {
    const {dom, errors, getConfig} = harness();
    try {
        await flush();
        const {document, Event} = dom.window;
        const input = document.querySelector('input[type=number]');
        assert.ok(input, 'plugin sensor must be shown');
        assert.match(document.querySelector('.saved').textContent, /Not configured/);
        input.value = '500';
        input.dispatchEvent(new Event('input', {bubbles: true}));
        assert.match(document.querySelector('.saved').textContent, /Unsaved change/);
        input.dispatchEvent(new Event('change', {bubbles: true}));
        await flush();
        assert.deepEqual(getConfig(), {max_watts: {[SENSOR]: 500}});
        assert.match(document.querySelector('.saved').textContent, /Saved maximum: 500 W/);
        assert.match(document.querySelector('#notice').textContent, /Settings saved/);
        assert.match(document.querySelector('.current').textContent, /40\.0°C virtual/);
        assert.deepEqual(errors, []);
    } finally {
        dom.window.close();
    }
});

test('stored wattage is visible when reopening the plugin page', async () => {
    const {dom, errors} = harness({max_watts: {[SENSOR]: 500}});
    try {
        await flush();
        const {document} = dom.window;
        assert.equal(document.querySelector('input[type=number]').value, '500');
        assert.match(document.querySelector('.saved').textContent, /Saved maximum: 500 W/);
        assert.doesNotMatch(document.querySelector('.saved').textContent, /Unsaved/);
        assert.deepEqual(errors, []);
    } finally {
        dom.window.close();
    }
});

test('failed saves remain visibly unsaved', async () => {
    const {dom, errors} = harness({}, false);
    try {
        await flush();
        const {document, Event} = dom.window;
        const input = document.querySelector('input[type=number]');
        input.value = '500';
        input.dispatchEvent(new Event('change', {bubbles: true}));
        await flush();
        assert.match(document.querySelector('#notice').textContent, /Save failed/);
        assert.match(document.querySelector('.saved').textContent, /Unsaved change/);
        assert.deepEqual(errors, []);
    } finally {
        dom.window.close();
    }
});

test('newly detected Intel GPU is listed alongside existing sources', async () => {
    const arc = 'temp-intel-arc';
    const cpu = 'temp-cpu';
    const {dom, errors, getConfig} = harness(
        {max_watts: {[SENSOR]: 228}},
        true,
        [
            [arc, {label: 'Intel GPU (i915) Power (power %)'}],
            [cpu, {label: 'CPU package-0 power (power %)'}],
        ],
    );
    try {
        await flush();
        const {document, Event} = dom.window;
        assert.equal(document.querySelectorAll('input[type=number]').length, 3);
        assert.match(document.querySelector('#sources').textContent, /Intel GPU \(i915\)/);
        assert.match(document.querySelector('#sources').textContent, /amdgpu PPT/);
        const intelInput = document.getElementById('max-' + arc);
        assert.ok(intelInput);
        intelInput.value = '190';
        intelInput.dispatchEvent(new Event('change', {bubbles: true}));
        await flush();
        assert.equal(getConfig().max_watts[arc], 190);
        assert.equal(getConfig().max_watts[SENSOR], 228);
        assert.deepEqual(errors, []);
    } finally {
        dom.window.close();
    }
});

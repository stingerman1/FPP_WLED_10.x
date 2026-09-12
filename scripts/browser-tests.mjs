// Run trusted repository browser scenarios against isolated local fixtures.
import {chromium} from 'playwright';
import {readFile, mkdir} from 'node:fs/promises';
import {spawn} from 'node:child_process';

const scenarios = ['theme_modes', 'fpp_wrapper', 'lighting_sync', 'settings_workflows',
  'node_type', 'segment_fields', 'layout_api', 'release_rollback', 'udp_discovery'];
const children = [];
const start = (command, args) => {
  const child = spawn(command, args, {stdio: ['ignore', 'inherit', 'inherit']});
  children.push(child);
  return child;
};
const stop = async child => {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  const exited = new Promise(resolve => child.once('exit', resolve));
  child.kill('SIGINT');
  const timer = setTimeout(() => child.kill('SIGKILL'), 10000);
  await exited;
  clearTimeout(timer);
};
const ready = async (url, predicate) => {
  for (let i = 0; i < 100; i++) {
    try {
      const response = await fetch(url);
      if (response.ok && (!predicate || predicate(await response.json()))) return;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw Error('Fixture failed to start: ' + url);
};
let browser;
try {
  if (!process.argv.includes('--existing-fixture')) {
    start('php', ['-S', '127.0.0.1:18789', 'tests/fixtures/fpp-router.php']);
  }
  browser = await chromium.launch();
  await mkdir('build/browser-results', {recursive: true});
  for (const name of scenarios.filter(name => !process.env.WLED_BROWSER_TEST || name === process.env.WLED_BROWSER_TEST)) {
    const fixture = process.argv.includes('--existing-fixture') ? null : start('python3', ['tests/ui_fixture.py']);
    await ready('http://localhost:18787/json/info');
    await ready('http://localhost:18787/api/status', status => status.allowed);
    await ready('http://localhost:18789/plugin.php?page=lights.php');
    const context = await browser.newContext({viewport: {width: 1280, height: 900}});
    await context.tracing.start({screenshots: true, snapshots: true});
    // Fixture tests cannot operate devices or navigate to a production FPP host.
    await context.route('**/*', route => {
      const url = new URL(route.request().url());
      return ['localhost', '127.0.0.1'].includes(url.hostname) ? route.continue() : route.abort();
    });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    try {
      await page.goto('http://localhost:18787/?view=lights');
      const source = await readFile(`tests/browser_${name}.js`, 'utf8');
      await new Function('return (' + source.trim().replace(/;$/, '') + ')')()(page);
      console.log('PASS browser_' + name);
    } catch (error) {
      await page.screenshot({path: `build/browser-results/${name}.png`, fullPage: true});
      throw error;
    } finally {
      await context.tracing.stop({path: `build/browser-results/${name}.zip`});
      await context.close();
      await stop(fixture);
    }
  }
} finally {
  await browser?.close();
  for (const child of children.reverse()) await stop(child);
}

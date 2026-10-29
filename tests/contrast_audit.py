#!/usr/bin/python3
"""Computed-style contrast fixtures in an offscreen WebKitGTK window.
Loads real App.css; never targets a desktop app or sends input. Fixture coverage
is explicit and does not certify arbitrary UI, artwork or screen-reader behavior.
"""
import argparse
import json
import hashlib
from pathlib import Path
import os
os.environ.setdefault('WEBKIT_DISABLE_DMABUF_RENDERER', '1')
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib


def over(front, back):
    alpha = front[3] + back[3] * (1 - front[3])
    return [((front[i] * front[3] + back[i] * back[3] * (1 - front[3])) / alpha if alpha else 0) for i in range(3)] + [alpha]


def contrast(a, b):
    def luminance(rgb):
        values = [v / 255 for v in rgb[:3]]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))
    x, y = sorted((luminance(a), luminance(b)))
    return (y + .05) / (x + .05)


def fixtures():
    cases = []
    def add(name, markup, threshold=4.5):
        cases.append(dict(name=name, markup=markup, threshold=threshold))
    for backdrop in ('#000000', '#ffffff'):
        for opacity in (.2, .8, .85, .92, 1):
            for name, markup in [
                ('clock-date', '<button class="clock-section interactive-widget"><time class="clock-date" data-target>Thu, Oct 29</time></button>'),
                ('clock-time', '<button class="clock-section interactive-widget"><time class="clock-time" data-target>23:59</time></button>'),
                ('clock-hover', '<button class="clock-section interactive-widget test-hover"><time class="clock-date" data-target>Thu, Oct 29</time></button>'),
                ('stats', '<div class="stat-pill"><span class="stat-text" data-target>100%</span></div>'),
                ('battery-action', '<button class="dock-action-btn system-widget-button"><small data-target>100%</small></button>'),
            ]:
                add(f'dock/{name}/{backdrop}/{opacity}', f'<div style="background:{backdrop}"><div class="taskbar-container" style="position:static;background:rgba(13,17,28,{opacity})">{markup}</div></div>')
    for name, markup in [
        ('dim', '<p class="brand-subtitle" data-target>Customize desktop</p>'),
        ('help', '<p class="settings-help" data-target>Help text</p>'),
        ('button', '<button data-target>Apply</button>'),
        ('button-hover', '<button class="test-hover" data-target>Apply</button>'),
        ('danger', '<button class="danger" data-target>Delete</button>'),
        ('input', '<input data-target value="Configuration">'),
        ('textarea', '<textarea data-target>application-class</textarea>'),
        ('range-output', '<label class="settings-range"><output data-target>100%</output></label>'),
    ]:
        add('studio/' + name, '<div class="studio-card" style="background:#1e293b">' + markup + '</div>')
    for backdrop in ('#000000', '#ffffff'):
        for surface, markup in [
            ('launcher', '<div class="app-launcher"><span data-target>Applications</span></div>'),
            ('launcher-selected-subtitle', '<div class="app-launcher"><div class="app-launcher-row is-selected"><button class="app-launcher-open"><span><small data-target>Application name</small></span></button></div></div>'),
            ('context', '<div class="context-actions"><button data-target>Open</button></div>'),
            ('context-danger', '<div class="context-actions"><button class="context-danger" data-target>Force quit</button></div>'),
            ('window-list', '<div class="window-list"><button data-target>Window title</button></div>'),
            ('window-active-status', '<div class="window-list"><div class="window-list-row is-active"><button class="window-list-select"><span><small data-target>Running</small></span></button></div></div>'),
            ('audio', '<div class="audio-popup"><span data-target>Audio</span></div>'),
            ('audio-help', '<div class="audio-popup"><p class="audio-help" data-target>Volume help</p></div>'),
            ('system-help', '<div class="audio-popup system-popup"><small data-target>System status</small></div>'),
            ('calendar-weekday', '<div class="calendar-flyout-card"><span class="calendar-weekday-cell" data-target>Mon</span></div>'),
            ('calendar-outside', '<div class="calendar-flyout-card"><button class="calendar-day-cell is-outside-month" data-target>31</button></div>'),
            ('calendar-today', '<div class="calendar-flyout-card"><button class="calendar-day-cell is-today" data-target>29</button></div>'),
        ]:
            add(f'popup/{surface}/{backdrop}', f'<div style="background:{backdrop}">{markup}</div>')
    return cases


def run(output, enforce, css_path, screenshot):
    css = css_path.read_text()
    cases = fixtures()
    assert len({case["name"] for case in cases}) == len(cases)
    markup = ''.join(f'<section data-case="{i}">{case["markup"]}</section>' for i, case in enumerate(cases))
    page = '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;"><style>' + css + '\n' + css.replace(':hover', '.test-hover') + '\n* {animation:none!important;transition:none!important}' + '</style>' + markup
    window = Gtk.OffscreenWindow()
    context = WebKit2.WebContext.new_ephemeral()
    view = WebKit2.WebView.new_with_context(context)
    window.add(view); window.set_default_size(900, 700); window.show_all()
    loop = GLib.MainLoop()
    result = {}
    script = r'''JSON.stringify(Array.from(document.querySelectorAll('[data-case]')).map(root=>{
      const target=root.querySelector('[data-target]'); const color=value=>{
        const parts=value.match(/[\d.]+/g).map(Number); if(parts.length===3)parts.push(1);return parts;
      }; const chain=[];
      for(let element=target;element;element=element.parentElement){const s=getComputedStyle(element);
        chain.push({background:color(s.backgroundColor),opacity:Number(s.opacity),image:s.backgroundImage});}
      return {index:Number(root.dataset.case),color:color(getComputedStyle(target).color),chain};
    }))'''
    def done(webview, task, *_):
        try:
            raw = json.loads(webview.evaluate_javascript_finish(task).to_string())
            for record in raw:
                bg = [0, 0, 0, 0]; fg = record['color']
                for layer in record['chain']:
                    assert layer['image'] == 'none', 'Gradient fixture requires a different measurement method'
                    bg, fg = over(bg, layer['background']), over(fg, layer['background'])
                    bg[3] *= layer['opacity']; fg[3] *= layer['opacity']
                bg, fg = over(bg, [255,255,255,1]), over(fg, [255,255,255,1])
                case = cases[record['index']]
                case.update(ratio=contrast(fg,bg), foreground=fg, background=bg, computed=record)
                case['passed'] = case['ratio'] >= case['threshold']
                del case['markup']
            result.update(cssSha256=hashlib.sha256(css.encode()).hexdigest(), ephemeralContext=True, engine=f'WebKitGTK {WebKit2.get_major_version()}.{WebKit2.get_minor_version()}.{WebKit2.get_micro_version()}', cases=cases,
                          passed=sum(c['passed'] for c in cases), total=len(cases), inputSent=False,
                          scope='Computed style fixtures using actual App.css in Gtk.OffscreenWindow; white/black backdrops, flat layers and group opacity. Hover selectors mapped to test-hover. No assertion of full app coverage, artwork, gradients, control borders, focus contrast, native widgets or screen-reader behavior.')
        except Exception as error:
            result['error'] = repr(error)
        if screenshot and 'error' not in result:
            selection = [c['name'] for c in cases if c['name'] in (
                'dock/clock-date/#ffffff/0.2', 'dock/clock-hover/#000000/1',
                'dock/stats/#ffffff/0.2', 'dock/battery-action/#ffffff/0.2')]
            selection_js = json.dumps([i for i,c in enumerate(cases) if c['name'] in selection])
            webview.evaluate_javascript("""(()=>{const all=Array.from(document.querySelectorAll('[data-case]'));const selected=""" + selection_js + """;
              document.body.replaceChildren(...selected.map(index=>all[index]));
              const style=document.createElement('style');style.textContent='html,body{background:#e2e8f0!important;overflow:auto!important}body{padding:24px;display:grid;grid-template-columns:1fr 1fr;gap:24px}section[data-case]{height:160px;min-width:0}h2{font-size:13px;color:#111827;margin:0 0 12px}';document.head.append(style);
              document.querySelectorAll('[data-case]').forEach(root=>{const label=document.createElement('h2');label.textContent=""" + json.dumps({str(i):c['name'] for i,c in enumerate(cases)}) + """[root.dataset.case];root.prepend(label);});return true;})()""", -1, None, None, None, snapshot_ready, None)
        else:
            loop.quit()
    def snapshot_ready(webview, task, *_):
        try:
            webview.evaluate_javascript_finish(task)
            webview.get_snapshot(WebKit2.SnapshotRegion.VISIBLE, WebKit2.SnapshotOptions.NONE, None, snapshot_done, None)
        except Exception as error:
            result['error'] = repr(error); loop.quit()
    def snapshot_done(webview, task, *_):
        try:
            surface = webview.get_snapshot_finish(task)
            surface.write_to_png(str(screenshot))
            result['screenshot'] = str(screenshot)
        except Exception as error:
            result['error'] = repr(error)
        loop.quit()
    def loaded(webview, event):
        if event == WebKit2.LoadEvent.FINISHED:
            webview.evaluate_javascript(script, -1, None, None, None, done, None)
    view.connect('load-changed', loaded)
    view.load_html(page, 'about:blank')
    def timeout():
        result['error'] = 'Offscreen WebKit audit timed out'; loop.quit(); return False
    timer = GLib.timeout_add_seconds(30, timeout)
    try:
        loop.run()
    finally:
        GLib.source_remove(timer); window.destroy()
    output.write_text(json.dumps(result, indent=2) + '\n')
    assert 'error' not in result, result
    print(json.dumps(dict(passed=result['passed'],total=result['total'],failures=[dict(name=c['name'],ratio=c['ratio']) for c in cases if not c['passed']])))
    if enforce:
        assert result['passed'] == result['total'], 'Contrast fixtures below 4.5:1'


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--enforce',action='store_true')
    parser.add_argument('--css',type=Path,default=Path(__file__).resolve().parents[1] / 'src/App.css')
    parser.add_argument('--screenshot',type=Path)
    args=parser.parse_args();run(args.output,args.enforce,args.css,args.screenshot)

"""Validate real WAV decoding, gesture unlocking, alarm priority and muting."""
import os
from playwright.sync_api import sync_playwright
BASE=os.environ.get('SAFESENSE_TEST_URL','http://127.0.0.1:8000')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page()
    page.add_init_script('''window.played=[];const original=AudioContext.prototype.createBufferSource;AudioContext.prototype.createBufferSource=function(){const source=original.call(this),start=source.start.bind(source);source.start=(...args)=>{window.played.push(source.buffer.duration);return start(...args)};return source};''')
    page.goto(BASE)
    page.locator('#showPassword').click()
    page.wait_for_timeout(300)
    result=page.evaluate('''async()=>{
      const s=await import('/static/sounds.js');await s.unlock();
      if(!s.settings().effects)s.toggle('effects');if(!s.settings().alerts)s.toggle('alerts');
      const wait=()=>new Promise(r=>setTimeout(r,150));
      const durations=[];
      for(const name of ['click','whoosh','pop','delete','confirm','warning','danger']){await wait();const before=played.length;await s.sound(name);durations.push(played.length-before);}
      s.resetAlarms();window.played=[];const now=Date.now();
      s.alarm([{id:1,status:'open',severity:'warning'}],now);await wait();const warning=played.length;
      s.alarm([{id:1,status:'open',severity:'warning'}],now+100);await wait();const debounced=played.length;
      s.alarm([{id:1,status:'acknowledged',severity:'warning'}],now+15000);await wait();const acknowledged=played.length;
      s.alarm([{id:2,status:'open',severity:'critical'}],now+30000);await wait();const critical=played.length;
      s.toggle('alerts');s.alarm([{id:3,status:'open',severity:'critical'}],now+60000);await wait();const muted=played.length;
      s.toggle('alerts');return {ready:s.settings().ready,durations,warning,debounced,acknowledged,critical,muted};
    }''')
    assert result['ready'] and result['durations']==[1]*7,result
    assert result['warning']==result['debounced']==result['acknowledged']==1,result
    assert result['critical']==result['muted']==4,result
    browser.close();print('PASS: all seven WAVs decode/play; gesture unlock, warning, critical pulses, debounce, acknowledgement and mute',result)

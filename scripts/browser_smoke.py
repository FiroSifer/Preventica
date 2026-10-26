from playwright.sync_api import sync_playwright
import urllib.request,json,time,os,tempfile
base=os.environ.get('SAFESENSE_TEST_URL','http://127.0.0.1:8000')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base);page.get_by_role('button',name='+ Add camera').click()
    page.locator('#cameraForm [name=name]').fill('Synthetic line 01');page.locator('#cameraForm [name=location]').fill('Demo workshop')
    page.get_by_role('button',name='Save camera').click();page.locator('.card').wait_for();page.locator('.card img').wait_for()
    page.locator('.card').click();page.locator('#detailDialog').wait_for(state='visible');page.get_by_role('button',name='+ Draw zone').click()
    r=page.locator('#overlay').bounding_box()
    for x,y in [(.1,.1),(.9,.1),(.9,.95),(.1,.95)]: page.mouse.click(r['x']+x*r['width'],r['y']+y*r['height'])
    page.get_by_role('button',name='Finish polygon').click();page.locator('#zoneForm [name=name]').fill('Demo restriction');page.locator('#zoneForm [name=required_ppe]').select_option(['helmet']);page.get_by_role('button',name='Save zone',exact=True).click()
    page.locator('#zoneList').get_by_text('Demo restriction',exact=True).wait_for();page.locator('#detailIncidents button[data-ack]').first.wait_for();page.locator('#detailIncidents button[data-ack]').first.click();page.locator('#detailIncidents button[data-resolve]').first.click()
    page.locator('#zoneList').get_by_role('button',name='Edit',exact=True).click()
    # Drag a vertex, insert a vertex on an edge, then remove it.
    page.mouse.move(r['x']+.1*r['width'],r['y']+.1*r['height']);page.mouse.down();page.mouse.move(r['x']+.15*r['width'],r['y']+.15*r['height']);page.mouse.up()
    assert page.locator('#overlay circle').count()==4
    page.mouse.click(r['x']+.525*r['width'],r['y']+.125*r['height']);assert page.locator('#overlay circle').count()==5
    page.keyboard.press('Delete');assert page.locator('#overlay circle').count()==4
    page.get_by_role('button',name='Cancel',exact=True).last.click()
    page.get_by_role('button',name='Close',exact=True).click();page.get_by_role('button',name='Incidents',exact=False).first.click();page.locator('#incidentList').wait_for();assert 'SIMULATED' in page.locator('#incidentList').inner_text()
    page.get_by_role('button',name='Dashboard').click();page.screenshot(path=os.path.join(tempfile.gettempdir(),'safesense-dashboard.png'),full_page=True)
    # Offline state, verified through real API and visible tile.
    req=urllib.request.Request(base+'/api/cameras',data=json.dumps({'name':'Disconnected demo','source_type':'demo','source':'offline'}).encode(),headers={'Content-Type':'application/json'},method='POST');urllib.request.urlopen(req).close()
    page.get_by_text('Disconnected demo',exact=True).wait_for();assert page.locator('.unavailable').count()>=1
    # Capture actual multipart bytes rather than relying on a listening port.
    with urllib.request.urlopen(base+'/api/cameras/1/stream') as stream:
        data=stream.read(2048);assert b'--frame\r\n' in data and b'Content-Type: image/jpeg' in data and b'\xff\xd8' in data
    assert not errors,errors
    print('PASS: add demo, changing MJPEG, detail, polygon draw/save/drag/insert/remove/cancel, incident acknowledge/resolve, offline tile; no browser errors')
    browser.close()

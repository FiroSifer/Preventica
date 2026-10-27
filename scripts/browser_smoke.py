"""Browser acceptance flow. Run only against a disposable local database."""
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
BASE=os.environ.get('SAFESENSE_TEST_URL','http://127.0.0.1:8000')
OUTPUT=Path(os.environ.get('SAFESENSE_TEST_OUTPUT','work/browser'))
OUTPUT.mkdir(parents=True,exist_ok=True)

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':900})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(BASE)
    page.locator('#loginName').fill('admin');page.locator('#loginPassword').fill('bad')
    page.locator('#signIn').click();expect(page.locator('#loginError')).to_contain_text('Incorrect')
    page.locator('#loginPassword').fill('admin');page.locator('#signIn').click()
    expect(page.locator('#appView')).to_be_visible()
    # Authenticated APIContext shares the browser's actual session cookies.
    api=page.context.request
    for cam in api.get(BASE+'/api/cameras').json():
        assert cam['source_type']=='demo','Use a fresh disposable database, not a real workspace.'
        api.delete(BASE+f"/api/cameras/{cam['id']}")
    page.reload();page.locator('#emptyDemo').click()
    expect(page.locator('.camera-card')).to_have_count(6)
    page.wait_for_function('Array.from(document.querySelectorAll(".camera-card img")).every(i=>i.naturalWidth>0)')
    # Verify controls still respond with six visible feeds.
    page.locator('#headingAdd').click();expect(page.locator('#cameraDialog')).to_be_visible()
    f=page.locator('#cameraForm')
    f.locator('[name=name]').fill('Invalid USB');f.locator('[name=location]').fill('QA Lab')
    f.locator('[name=source]').fill('99');page.locator('#saveCamera').click()
    expect(f.locator('.form-error')).to_contain_text('USB camera',timeout=15000)
    expect(page.locator('.camera-card')).to_have_count(6)
    f.locator('[data-close]').first.click()
    # Reproducible zone shape, name/type, movement and cancel semantics.
    page.locator('.camera-card').first.click();expect(page.locator('#detailDialog')).to_be_visible()
    page.locator('#addZone').click();zone=page.locator('#zoneForm')
    zone.locator('[name=name]').fill('QA perimeter')
    zone.locator('[name=type]').select_option('restricted')
    zone.locator('[name=severity]').select_option('critical')
    bounds=page.locator('#overlay').bounding_box()
    for x,y in [(.12,.14),(.82,.14),(.82,.92),(.12,.92)]:
        page.mouse.click(bounds['x']+x*bounds['width'],bounds['y']+y*bounds['height'])
    page.locator('#finishPolygon').click();zone.locator('button.primary').click()
    expect(page.locator('#zoneList')).to_be_visible();expect(page.locator('#zoneList')).to_contain_text('QA perimeter')
    camera_id=api.get(BASE+'/api/cameras').json()[0]['id']
    saved=api.get(BASE+f'/api/cameras/{camera_id}/zones').json()[0]
    assert saved['name']=='QA perimeter' and saved['type']=='restricted'
    page.locator('#zoneList button').first.click();zone.locator('[name=name]').fill('Unsaved name')
    # Move a vertex.
    page.mouse.move(bounds['x']+.12*bounds['width'],bounds['y']+.14*bounds['height']);page.mouse.down()
    page.mouse.move(bounds['x']+.16*bounds['width'],bounds['y']+.19*bounds['height']);page.mouse.up()
    page.locator('#cancelZone').click()
    assert api.get(BASE+f'/api/cameras/{camera_id}/zones').json()[0]['polygon']==saved['polygon']
    expect(page.locator('#zoneList')).to_contain_text('QA perimeter')
    page.locator('#zoneList button').first.click();zone.locator('[name=name]').fill('QA revised')
    zone.locator('[name=type]').select_option('danger')
    page.mouse.move(bounds['x']+.12*bounds['width'],bounds['y']+.14*bounds['height']);page.mouse.down()
    page.mouse.move(bounds['x']+.16*bounds['width'],bounds['y']+.19*bounds['height']);page.mouse.up()
    zone.locator('button.primary').click();expect(page.locator('#zoneList')).to_contain_text('QA revised')
    revised=api.get(BASE+f'/api/cameras/{camera_id}/zones').json()[0]
    assert revised['type']=='danger' and revised['polygon']!=saved['polygon']
    # Close-with-X discards a new draft.
    page.locator('#addZone').click();zone.locator('[name=name]').fill('Discard on close')
    page.locator('#detailDialog [data-close]').click()
    assert len(api.get(BASE+f'/api/cameras/{camera_id}/zones').json())==1
    # Incident workflow uses real persisted engine outputs.
    page.locator('#activityButton').click();expect(page.locator('#incidentList .incident-row').first).to_be_visible(timeout=15000)
    ack=page.locator('#incidentList [data-ack]').first;ack.click()
    expect(page.locator('#incidentList')).to_contain_text('acknowledged')
    page.locator('#incidentList [data-resolve]').first.click()
    expect(page.locator('#incidentList')).to_contain_text('resolved')
    page.locator('#activityDialog [data-close]').click()
    # Light theme persists across reload.
    page.locator('#pinSidebar').click();page.locator('#themeToggle').click()
    assert page.locator('body').evaluate('e=>e.classList.contains("light")')
    page.reload();expect(page.locator('.camera-card')).to_have_count(6)
    assert page.locator('body').evaluate('e=>e.classList.contains("light")')
    page.locator('#pinSidebar').click();page.locator('#themeToggle').click()
    # Cancel and confirm removal, then exit deletion mode by clicking it again.
    page.locator('#pinSidebar').click();page.locator('#deleteMode').click()
    page.locator('.remove-camera').last.click();page.locator('#confirmDialog button[data-close]').last.click()
    expect(page.locator('.camera-card')).to_have_count(6)
    page.locator('.remove-camera').last.click();page.locator('#confirmDelete').click()
    expect(page.locator('.camera-card')).to_have_count(5)
    page.locator('#pinSidebar').click();page.locator('#deleteMode').click()
    expect(page.locator('#deleteBanner')).to_be_hidden()
    assert len(api.get(BASE+'/api/cameras').json())==5
    # Three feeds: one large on top, two below. All counts remain in the viewport.
    cams=api.get(BASE+'/api/cameras').json()
    for cam in cams[3:]: api.delete(BASE+f"/api/cameras/{cam['id']}")
    page.reload();expect(page.locator('.camera-card')).to_have_count(3)
    assert page.locator('.camera-row').nth(0).locator('.camera-card').count()==1
    assert page.locator('.camera-row').nth(1).locator('.camera-card').count()==2
    assert page.evaluate('document.body.scrollHeight')==900
    page.screenshot(path=str(OUTPUT/'three-camera-layout.png'))
    for width,height in [(1440,900),(1024,768),(390,844)]:
        page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(350)
        assert page.evaluate('document.body.scrollHeight')==height
        for box in page.locator('.camera-card').all():
            rect=box.bounding_box();assert rect['y']+rect['height']<=height
        assert page.evaluate('document.documentElement.scrollWidth')==width
    page.set_viewport_size({'width':1440,'height':900})
    # Dashboard is the default full-width view; navigation reveals in two stages.
    page.mouse.move(700,400);page.wait_for_timeout(350)
    assert page.locator('#sidebar').bounding_box()['x']<0
    page.mouse.move(80,400);page.wait_for_timeout(350)
    assert 58<=page.locator('#sidebar').bounding_box()['width']<=62
    page.mouse.move(30,400);page.wait_for_timeout(350)
    assert page.locator('#sidebar').bounding_box()['width']==224
    page.mouse.move(700,400);page.wait_for_timeout(350)
    assert page.locator('#sidebar').bounding_box()['x']<0
    assert page.locator('#cameraGrid').bounding_box()['width']>1400
    assert page.locator('#openSystem').count()==0
    # Overlay visibility is shared, persists, and never mutates zone configuration.
    zones_before=api.get(BASE+f'/api/cameras/{camera_id}/zones').json()
    page.locator('#pinSidebar').click();page.locator('#toggleOverlays').click()
    assert page.locator('body').evaluate('e=>e.classList.contains("overlays-hidden")')
    page.locator('.camera-card').first.click()
    expect(page.locator('#detailOverlays')).to_have_attribute('aria-pressed','false')
    expect(page.locator('#overlay')).to_have_css('opacity','0')
    page.locator('#addZone').click()
    expect(page.locator('#overlay')).to_have_css('opacity','1')
    page.locator('#cancelZone').click()
    page.locator('#detailOverlays').click()
    expect(page.locator('#detailOverlays')).to_have_attribute('aria-pressed','true')
    page.locator('#detailDialog [data-close]').click()
    expect(page.locator('#detailDialog')).to_be_hidden()
    assert api.get(BASE+f'/api/cameras/{camera_id}/zones').json()==zones_before
    # Every workspace and form fits without scrolling at representative sizes.
    def fits(selector):
        assert page.locator(selector).evaluate('e=>e.scrollHeight<=e.clientHeight+1 && e.scrollWidth<=e.clientWidth+1'),selector
    for width,height in [(1440,900),(1366,768),(1024,768),(390,844),(375,667),(844,390)]:
        page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(350)
        page.locator('.camera-card').first.click();page.wait_for_timeout(500)
        for selector in ['#detailDialog','.detail-layout','.detail-left','.report-panel','#reportView','#findingsPanel','#detailIncidents']:
            fits(selector)
        page.locator('#addZone').click();page.screenshot(path=str(OUTPUT/f'zone-{width}x{height}.png'));fits('#zoneForm');fits('.report-panel')
        page.locator('#cancelZone').click()
        page.locator('#detailDialog [data-close]').click();expect(page.locator('#detailDialog')).to_be_hidden()
        page.locator('#headingAdd').click();fits('#cameraDialog')
        page.locator('#cameraDialog [data-close]').first.click();expect(page.locator('#cameraDialog')).to_be_hidden()
        page.locator('#activityButton').click();page.wait_for_timeout(100)
        fits('#activityDialog');fits('#incidentList')
        page.locator('#activityDialog [data-close]').click();expect(page.locator('#activityDialog')).to_be_hidden()
    page.set_viewport_size({'width':1440,'height':900})
    page.locator('#pinSidebar').click();page.locator('#logout').click()
    expect(page.locator('#loginView')).to_be_visible()
    assert api.get(BASE+'/api/cameras').status==401
    assert not errors,errors
    browser.close()
    print('PASS: login, six responsive feeds, invalid USB rejection, zone draw/save/move/cancel/type, close discard, incident lifecycle, themes, delete/cancel, adaptive layout, hidden navigation, shared overlays, viewport-fitted dialogs, logout; no JS errors')

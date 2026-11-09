#!/usr/bin/env python3
"""Exercise rotation on a private bus; no host services or displays are changed."""
import json, os, pathlib, subprocess, sys, tempfile, time
SOURCE = pathlib.Path(__file__).resolve().parents[2] / 'packages/starch-rotation/root/usr/lib/starch/rotation.py'
SERVER = r'''
import json, os
from pathlib import Path
from gi.repository import Gio, GLib
bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
xml = ''' + "'''" + '''<node>
<interface name="org.freedesktop.login1.Manager"><method name="GetSessionByPID"><arg type="u" direction="in"/><arg type="o" direction="out"/></method><method name="ListSessions"><arg type="a(susso)" direction="out"/></method></interface>
<interface name="org.freedesktop.DBus.Properties"><method name="GetAll"><arg type="s" direction="in"/><arg type="a{sv}" direction="out"/></method></interface>
<interface name="net.hadess.SensorProxy"><method name="ClaimAccelerometer"/><method name="ReleaseAccelerometer"/></interface>
</node>''' + "'''" + r'''
info = Gio.DBusNodeInfo.new_for_xml(xml)
def method(conn, sender, path, interface, name, params, invocation):
 state = json.loads(Path(os.environ['STATE']).read_text())
 if name == 'GetSessionByPID' and state.get('unscoped'):
  invocation.return_dbus_error('org.freedesktop.login1.NoSessionForPID', 'User service has no session scope')
  return
 if name == 'ListSessions':
  result = GLib.Variant('(a(susso))', ([('test', os.getuid(), 'tester', 'seat0', '/session/test')],))
 elif name == 'GetSessionByPID':
  result = GLib.Variant('(o)', ('/session/test',))
 elif name == 'GetAll':
  values = ({'Type': GLib.Variant('s', 'wayland'), 'Active': GLib.Variant('b', state['active']), 'LockedHint': GLib.Variant('b', state['locked'])}
            if path.startswith('/session') else
            {'HasAccelerometer': GLib.Variant('b', state['sensor']), 'AccelerometerOrientation': GLib.Variant('s', state['orientation'])})
  result = GLib.Variant('(a{sv})', (values,))
 else:
  with open(os.environ['EVENTS'], 'a') as f: f.write(name + '\n')
  result = GLib.Variant('()', ())
 invocation.return_value(result)
for name in ('org.freedesktop.login1', 'net.hadess.SensorProxy'):
 bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','RequestName',GLib.Variant('(su)',(name,0)),None,Gio.DBusCallFlags.NONE,3000,None)
for path in ('/org/freedesktop/login1','/session/test','/net/hadess/SensorProxy'):
 for interface in info.interfaces:
  bus.register_object(path, interface, method, None, None)
Path(os.environ['READY']).touch()
GLib.MainLoop().run()
'''
WORKER = r'''
import importlib.util, os
spec=importlib.util.spec_from_file_location('rotation', os.environ['SOURCE'])
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Display:
 def __init__(self,kind): pass
 def apply(self,orientation,config):
  with open(os.environ['EVENTS'],'a') as f: f.write('apply:'+orientation+'\n')
m.Display=Display
m.run('cosmic')
'''
with tempfile.TemporaryDirectory(prefix='rotation-bus-') as directory:
 root=pathlib.Path(directory)
 processes=[]
 try:
  bus=subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,text=True);processes.append(bus)
  address=bus.stdout.readline().strip()
  if not address:
   raise RuntimeError('Cannot start private D-Bus; this test needs permission to bind a temporary Unix socket.')
  env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=address,STATE=str(root/'state'),EVENTS=str(root/'events'),READY=str(root/'ready'),SOURCE=str(SOURCE),XDG_CONFIG_HOME=str(root/'config'))
  env.pop('XDG_SESSION_ID',None)
  state={'active':True,'locked':False,'sensor':False,'orientation':'left-up'}
  def save():
   (root/'temp').write_text(json.dumps(state));(root/'temp').replace(root/'state')
  def events(): return (root/'events').read_text() if (root/'events').exists() else ''
  def wait_for(predicate):
   deadline=time.monotonic()+12
   while time.monotonic()<deadline:
    if predicate(): return
    time.sleep(.1)
   raise AssertionError(events())
  save()
  server=subprocess.Popen([sys.executable,'-c',SERVER],env=env);processes.append(server)
  wait_for(lambda:(root/'ready').exists())
  worker=subprocess.Popen([sys.executable,'-c',WORKER],env=env);processes.append(worker)
  time.sleep(1); assert not events(), events()
  state['sensor']=True;save()
  wait_for(lambda:'apply:left-up' in events())
  state['unscoped']=True
  state['locked']=True;save()
  wait_for(lambda:'ReleaseAccelerometer' in events())
  count=events().count('apply:');time.sleep(5.5);assert events().count('apply:')==count
  state['locked']=False;save()
  wait_for(lambda:events().count('ClaimAccelerometer')==2)
  wait_for(lambda:events().count('apply:')>count)
  worker.terminate();worker.wait(timeout=5)
  assert events().count('ReleaseAccelerometer')==2,events()
  print('Private D-Bus integration passed: absent sensor, late sensor, claim, apply, lock/release, unlock/reclaim, user-service session discovery, graceful cleanup.')
 finally:
  for process in reversed(processes):
   if process.poll() is None:
    process.terminate();process.wait(timeout=5)

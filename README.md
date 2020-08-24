# weewx-acs758

### Dash App Installation Instructions

In order to run the dash app, you must have python installed on your raspberry pi,
or other runtime environment.  Additionally, you must install two additional libraries:

```
sudo pip install requests
sudo pip install pymodbus
```

Then simply run with:

```
python app.py
```

It will by default listen on port 8050

To enable your browser to startup in full screen and point to this app immediately, I use the following script:

```
python ~/weewx-acs758/src/dash-app/app.py &
sleep 10
chromium-browser --start-fullscreen http://localhost:8050
```

Then I create a new file:

~/.config/lxsession/LXDE-pi/autostart

with the content:

```
@lxterminal -e ~/run_monitor.sh
```


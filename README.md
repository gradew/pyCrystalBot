Information
===========

Python version of the official CrystalIRC bot

Created by Julien Derivière (gradew@crystalirc.net)

pyCrystalBot is a Python IRC client that can be used as a bot on UnrealIRCd IRC servers.

Installation
============
You will need the following:
- jquery.min.js, in the js/ subfolder
- the complete Twitter Bootstrap package, in the bootstrap/ subfolder

Configuration
=============
pyCrystalBot will load its configuration from pyCrystalBot.cfg.
pyCrystalBot.cfg-dist contains a sample configuration for your reference.
You will need to rename it to "pyCrystalBot.cfg" and adjust the settings.

Embedded web server
===================
pyCrystalBot also creates a web socket so the users or administrators can query it,
or send instructions to it.

It uses Flask to serve dynamic templates, but static content is also used.
You will need to download the full Twitter Bootstrap package and unzip it to
/opt/pyCrystalBot/bootstrap, and configure nginx as a reverse proxy as follows:

    server {
        listen 80;
        server_name localhost;
        location /users {
            proxy_pass         http://127.0.0.1:5000/users;
        }
        location /say {
            proxy_pass         http://127.0.0.1:5000/say;
        }
        location /mode {
            proxy_pass         http://127.0.0.1:5000/mode;
        }
        location /kick {
            proxy_pass         http://127.0.0.1:5000/kick;
        }
        location /css {
            root /opt/pyCrystalBot/;
        }
        location /bootstrap {
            root /opt/pyCrystalBot/;
        }
    }

Sending messages through the web socket
=======================================

wget -O - --quiet --post-data='dst=#channel&msg=Hello, there!' http://localhost/say > /dev/null


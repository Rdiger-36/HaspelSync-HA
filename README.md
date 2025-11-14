To use this Add On you need HACS.
For installation just copy the repo url and add a custom repositorie in HACS.
Search for Bambu AMS Monitoring, and install this Integration.

1. Go to Settings -> Devices
2. Add new integration: Bambu AMS Monitoring Integration
3. Put in your base_url of your service:
	like this:
	- https://ams-server.com
	- https://myserver.com/ams
	- https://ams-server.com:8443
	- http://192.168.1.100:4000

4. Select your printer
5. Enjoy your toogle switch

This Add On depends on a working https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus environment

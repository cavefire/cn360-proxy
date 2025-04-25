# 360 / Qihoo / Botslab 360 Vacuum Robot Proxy

This tool provides a proxy for your vacuum robot, enabling local control without roundtrips to China.
It does not disable the app.

### Tested Devices
- 360 S9

Other devices may also work, but they have not been tested.

---

## Installation

```bash
git clone https://github.com/cavefire/cn360-proxy.git
cd cn360-proxy 
```

Now edit the "docker-compose.yml" file with your editor of choice.
All variables you have to modify have been marked with a "!" as well as a description of their function.

Then you can start the container with 
```bash
docker compose up -d
```

After that you will have to forward all traffic from the robot through your server. That can be done in your router by configuring a custom route. 

Otherwise you can create a VLAN and set your server's ip as the default gateway. In that case your server must be in the same VLAN (at least one interface).
When thats done, create iptables rules like this:

```bash
iptables -t nat -A POSTROUTING -s "$ROBOT_IP" -o "$INTF" -j MASQUERADE
iptables -t nat -A PREROUTING -s "$ROBOT_IP" -p tcp --dport 80  -j REDIRECT --to-port "$PROXY_PORT"
iptables -t nat -A PREROUTING -s "$ROBOT_IP" -p tcp --dport 443 -j REDIRECT --to-port "$PROXY_PORT"
```
where ...
- $INTF is your interface (e.g. eth0 - in the VLAN of your robot)
- $ROBOT_IP is the ip of your robot (reserve an ip in your dhcp / router for your robot)
- $PROXY_PORT is the port of your proxy from the `docker-compose.yml` file

You can then save the configuration with `iptables-save > /etc/iptables/rules.v4`

Now make sure you restart your robot. Do it like this:
1. Remove it from the charging dock
2. Use something pointy to press the reset button (open the top cover, on the right side of the buttons)
3. Wait approximately one minute
4. Press and hold the power button for around 5-10 seconds, until you hear a sound.

Now enter `docker compose logs -f --tail 10` in your server's console. You should see a message, that the robot is connected. If not, check all your routing.
The WiFi-LED of the robot should be on constantly. If it is flashing, it is not connected to the cloud server. Again, check your routing.

## How does it work?
All tcp traffic from your robot is routed through your server now. Therefor we have access to all the traffic of the robot and can intercept it.

First the robot is fetching a ip and port of the control server of Qihoo. The response is modified to point towards your server and your server opens the connection to the real server.
The robot then connects to your server, which relays all messages from Qihoo's server to your robot and the other way around. But we now have a way to send our own commands to the robot.

Since the commands are encrypted, the proxy also catches the registration of the robot in the cloud and saves the encryption key. This key is stored in the file "pushkey.txt" and wil change on every reboot of the robot. The proxy will save it every time it sees a new key.

The robot does not send its status via the server. It does make https requests instead. These are even easier to capture and forward to the local control server.

## Interfacing with the local control server

- Open a connection with the server (port is configured in `docker-compose.yml`)
- Wait for messages
      The first 2 bytes of each message are 0x1616 as the magic, followed by 2 bytes defining the payload length. After that the payload is in json format, as it comes from the robot
- To send a command to the robot, just send a json request. No header or trailer needed.

## Contributing
This project is a work in progress, and contributions are welcome!
If you encounter issues, have feature requests, or want to contribute, feel free to submit a pull request or open an issue.

## Disclaimer
This project is not affiliated with Qihoo 360 Technology Co. Ltd. The API and all functions are reverse-engineered and may break at any time. Use at your own risk.

**To the Qihoo 360 legal team:**
I found out all the functions with my own device and did not use any copyright-protected data. This activity is legally protected in Germany.
However, if there are any concerns, we will surely find a way to mitigate them together.

## License
This project is licensed under GNU GPLv3 - see the [LICENSE](LICENSE) file for details.

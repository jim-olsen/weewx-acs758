#include <WiFiNINA.h>
#include <SPI.h>
#include <WiFiNINA.h>

#include "arduino_secrets.h" 
char ssid[] = SECRET_SSID;        // your network SSID (name)
char pass[] = SECRET_PASS;    // your network password (use for WPA, or use as key for WEP)
int keyIndex = 0;                 // your network key Index number (needed only for WEP)
IPAddress ipAddr(10, 0, 10, 33);
IPAddress dnsAddr(10, 0, 10, 31);
IPAddress gwAddr(10, 0, 10, 254);
IPAddress netMask(255, 255, 255, 0);

int status = WL_IDLE_STATUS;
WiFiServer server(80);

void setup() {
  Serial.begin(9600);      // initialize serial communication
  pinMode(A0, INPUT);
  pinMode(A1, INPUT);
  pinMode(A2, INPUT);
  pinMode(A3, INPUT);
  pinMode(A4, INPUT);
  pinMode(A5, INPUT);

  // check for the WiFi module:
  if (WiFi.status() == WL_NO_MODULE) {
    Serial.println("Communication with WiFi module failed!");
    // don't continue
    while (true);
  }

  String fv = WiFi.firmwareVersion();
  if (fv != "1.0.0") {
    Serial.println("Please upgrade the firmware");
  }

  // attempt to connect to Wifi network:
  while (status != WL_CONNECTED) {
    Serial.print("Attempting to connect to Network named: ");
    Serial.println(ssid);                   // print the network name (SSID);

    // Configure our IP address
    WiFi.config(ipAddr, dnsAddr, gwAddr, netMask);
    // Connect to WPA/WPA2 network. Change this line if using open or WEP network:
    status = WiFi.begin(ssid, pass);
    // wait 10 seconds for connection:
    delay(10000);
  }
  server.begin();                           // start the web server on port 80
  printWifiStatus();                        // you're connected now, so print out the status
}

void printWifiStatus() {
  // print the SSID of the network you're attached to:
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());

  // print your WiFi shield's IP address:
  IPAddress ip = WiFi.localIP();
  Serial.print("IP Address: ");
  Serial.println(ip);
  IPAddress netmask = WiFi.subnetMask();
  Serial.print("Netmask: ");
  Serial.println(netmask);
  IPAddress gwIp = WiFi.gatewayIP();
  Serial.print("GW Address: ");
  Serial.println(gwIp);

  // print the received signal strength:
  long rssi = WiFi.RSSI();
  Serial.print("signal strength (RSSI):");
  Serial.print(rssi);
  Serial.println(" dBm");
  // print where to go in a browser:
  Serial.print("To see this page in action, open a browser to http://");
  Serial.println(ip);
}

float getAmps(int portNum) {
  int sensorValue = analogRead(portNum);

  float rawVoltage = sensorValue * (5.0 / 1023.0);
  float voltage = rawVoltage - (0.5 * 5.0) + .007;

  float amps = voltage / (20.0 / 1000.0);

  return amps;
}

void loop() {
  String outputLine;
  WiFiClient client = server.available();   // listen for incoming clients

  if (client) {                             // if you get a client,
    Serial.println("new client");           // print a message out the serial port
    String currentLine = "";                // make a String to hold incoming data from the client
    while (client.connected()) {            // loop while the client's connected
      if (client.available()) {             // if there's bytes to read from the client,
        char c = client.read();             // read a byte, then
        Serial.write(c);                    // print it out the serial monitor
        if (c == '\n') {                    // if the byte is a newline character

          // if the current line is blank, you got two newline characters in a row.
          // that's the end of the client HTTP request, so send a response:
          if (currentLine.length() == 0) {
            // HTTP headers always start with a response code (e.g. HTTP/1.1 200 OK)
            // and a content-type so the client knows what's coming, then a blank line:
            if (outputLine.length() == 0) {
            client.println("HTTP/1.1 200 OK");
            client.println("Content-type:text/html");
            client.println();

            // the content of the HTTP response follows the header:
            client.println("<html>");
            client.println("<head>");
            client.println("<script>");
            client.println("function callREST() {");
            client.println("  var xhttp = new XMLHttpRequest();");
            client.println("  xhttp.onreadystatechange = function() {");
            client.println("    if (this.readyState == 4 && this.status == 200) {");
            client.println("      var divElem = document.getElementById(\"response\")");
            client.println("      divElem.innerHTML = this.responseText;");
            client.println("    }");
            client.println("  };");
            client.println("  var pinNum = document.getElementById(\"pin\").value;");
            client.println("  xhttp.open(\"GET\", \"/A\" + pinNum, true); xhttp.send();");
            client.println("}");
            client.println("</script>");
            client.println("</head>");

            client.println("<body>");
            client.println("<form>");
            client.println("Input Pin:<br>");
            client.println("<input type=\"text\" id=\"pin\"><br>");
            client.println("<button type=\"button\" onclick=\"callREST()\">Get Amps</button>");
            client.println("</form>");
            client.println("<div id=\"response\"></div>");
            client.println("</body>");
            client.println("</html>");

            // The HTTP response ends with another blank line:
            client.println();
            // break out of the while loop:
            break;
            } else {
            client.println("HTTP/1.1 200 OK");
            client.println("Content-type:application/json");
            client.println();
            client.println(outputLine);
            client.println();
            break;
            }
          } else {    // if you got a newline, then clear currentLine:
            currentLine = "";
          }
        } else if (c != '\r') {  // if you got anything else but a carriage return character,
          currentLine += c;      // add it to the end of the currentLine
        }

        if (currentLine.endsWith("GET /READALL")) {
          char strbuf[255];

          outputLine+= "{ ";
          outputLine+= "\"A0\": ";
          outputLine+= dtostrf(getAmps(0),4, 2, strbuf);
          outputLine+= ", \"A1\": ";
          outputLine+= dtostrf(getAmps(1),4, 2, strbuf);
          outputLine+= ", \"A2\": ";
          outputLine+= dtostrf(getAmps(2),4, 2, strbuf);
          outputLine+= ", \"A3\": ";
          outputLine+= dtostrf(getAmps(3),4, 2, strbuf);
          outputLine+= ", \"A4\": ";
          outputLine+= dtostrf(getAmps(4),4, 2, strbuf);
          outputLine+= ", \"A5\": ";
          outputLine+= dtostrf(getAmps(5),4, 2, strbuf);
          outputLine+= " }";
        }
        if (currentLine.substring(0, currentLine.length()-1).endsWith("GET /A")) {
          char strbuf[255];
          int portNum;
          sscanf(currentLine.substring(currentLine.length() - 2).c_str(), "A%d", &portNum);
          outputLine+= "{\"A";
          outputLine+= portNum;
          outputLine+= "\": ";
          outputLine+= dtostrf(getAmps(portNum), 4, 2, strbuf);
          outputLine+= " }";
        }
      }
    }
    // close the connection:
    client.stop();
    Serial.println("client disonnected");
  }
}
using UnityEngine;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.IO;
using System.Collections.Generic;
using Newtonsoft.Json;

public class NetworkHandler : MonoBehaviour
{
    Thread serverThread;

    void Start()
    {
        serverThread = new Thread(new ThreadStart(ServerThread));
        serverThread.Start();
    }

    void ServerThread()
    {
        TcpListener listener = new TcpListener(IPAddress.Parse("127.0.0.1"), 5005);
        listener.Start();
        while (true)
        {
            using (TcpClient client = listener.AcceptTcpClient())
            using (NetworkStream stream = client.GetStream())
            {
                byte[] buffer = new byte[4096];
                int bytesRead = stream.Read(buffer, 0, buffer.Length);
                string json = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                var parameters = JsonConvert.DeserializeObject<Dictionary<string, int[]>>(json);

                // Run simulation with parameters...
                float score = RunSimulation(parameters);

                var result = new { fitness = score };
                string response = JsonConvert.SerializeObject(result);
                byte[] sendData = Encoding.UTF8.GetBytes(response);
                stream.Write(sendData, 0, sendData.Length);
            }
        }
    }

    float RunSimulation(Dictionary<string, int[]> p)
    {
        // Placeholder for Unity logic
        return p["passenger_sequence"][0];
    }
}

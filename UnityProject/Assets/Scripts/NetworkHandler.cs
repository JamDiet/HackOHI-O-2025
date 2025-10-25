using UnityEngine;
using System;
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
    public GeneratePath pathGenerator;

    // Thread-safe queue for actions that must run on main thread
    private readonly Queue<Action> mainThreadActions = new Queue<Action>();

    void Start()
    {
        serverThread = new Thread(ServerThread);
        serverThread.IsBackground = true;
        serverThread.Start();
    }

    void Update()
    {
        // Execute queued actions on main thread
        lock (mainThreadActions)
        {
            while (mainThreadActions.Count > 0)
            {
                mainThreadActions.Dequeue()?.Invoke();
            }
        }
    }

    void ServerThread()
    {
        TcpListener listener = new TcpListener(IPAddress.Parse("127.0.0.1"), 5555);
        listener.Start();
        Debug.Log("Server listening on port 5555");

        while (true)
        {
            using (TcpClient client = listener.AcceptTcpClient())
            using (NetworkStream stream = client.GetStream())
            {
                byte[] buffer = new byte[4096];
                int bytesRead = stream.Read(buffer, 0, buffer.Length);
                string json = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                var parameters = JsonConvert.DeserializeObject<Dictionary<string, int[]>>(json);

                // Use synchronization primitive to wait for Unity main thread
                AutoResetEvent doneEvent = new AutoResetEvent(false);
                float time = 0f;

                // Queue simulation to run on Unity main thread
                lock (mainThreadActions)
                {
                    mainThreadActions.Enqueue(() =>
                    {
                        StartCoroutine(RunSimulationCoroutine(parameters, result =>
                        {
                            time = result;
                            doneEvent.Set();
                        }));
                    });
                }

                // Wait until coroutine finishes
                doneEvent.WaitOne();

                // Send time back to Python
                var resultObj = new { time = time };
                string response = JsonConvert.SerializeObject(resultObj) + "\n";
                byte[] sendData = Encoding.UTF8.GetBytes(response);
                stream.Write(sendData, 0, sendData.Length);
                stream.Flush();
            }
        }
    }

    private System.Collections.IEnumerator RunSimulationCoroutine(Dictionary<string, int[]> p, Action<float> callback)
    {
        // Run your coroutine on the main thread
        yield return StartCoroutine(pathGenerator.RunSimulation(p["passenger_sequence"]));

        // Once finished, get time from pathGenerator
        float score = pathGenerator.GetScore(); // implement this in your GeneratePath class
        callback?.Invoke(score);
    }

    void OnApplicationQuit()
    {
        if (serverThread != null && serverThread.IsAlive)
        {
            serverThread.Abort();
        }
    }
}

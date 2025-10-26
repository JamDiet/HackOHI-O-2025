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
            TcpClient client = listener.AcceptTcpClient();
            NetworkStream stream = client.GetStream();
            Debug.Log("Client connected");

            StreamReader reader = new StreamReader(stream, Encoding.UTF8);
            StreamWriter writer = new StreamWriter(stream, Encoding.UTF8) { AutoFlush = true };

            while (true)
            {
                string line;
                try
                {
                    line = reader.ReadLine(); // read until newline
                    if (line == null) break; // client disconnected

                    var parameters = JsonConvert.DeserializeObject<Dictionary<string, int[]>>(line);
                    float time = 0f;
                    float[] timePerPassenger = new float[] {};

                    // enqueue on main thread
                    AutoResetEvent doneEvent = new AutoResetEvent(false);
                    lock (mainThreadActions)
                    {
                        mainThreadActions.Enqueue(() =>
                        {
                            StartCoroutine(RunSimulationCoroutine(parameters, result =>
                            {
                                time = result.time;
                                timePerPassenger = result.timePerPassenger;
                                doneEvent.Set();
                            }));
                        });
                    }
                    doneEvent.WaitOne();

                    // send back result
                    var resultObj = new { time = time, time_per_passenger = timePerPassenger };
                    string response = JsonConvert.SerializeObject(resultObj);
                    writer.WriteLine(response);
                }
                catch (Exception e)
                {
                    Debug.LogWarning($"Client message error: {e.Message}");
                    break;
                }
            }

            stream.Close();
            client.Close();
            Debug.Log("Client disconnected");
        }

    }


    private System.Collections.IEnumerator RunSimulationCoroutine(Dictionary<string, int[]> p, Action<(float time, float[] timePerPassenger)> callback)
    {
        // Run your coroutine on the main thread
        yield return StartCoroutine(pathGenerator.RunSimulation(p["passenger_sequence"]));

        // Once finished, get time from pathGenerator
        (float time, float[] timePerPassenger) score = pathGenerator.GetScore(); // implement this in your GeneratePath class
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

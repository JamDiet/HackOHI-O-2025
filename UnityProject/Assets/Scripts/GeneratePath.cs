using UnityEngine;
using System.Collections;
using System.Collections.Generic;

public class GeneratePath : MonoBehaviour
{
    public GameObject nodePre;
    public GameObject seatPre;
    public GameObject passengerPre;
    public GameObject wingPre;
    public Transform startNode;
    public Transform queueNode;
    public Transform tail;
    public int steps;
    public int[] timePerPassenger;
    public List<(Vector2 pos, int[] connectedSeats)> pathData;
    public List<Passenger> allPassengers;
    public List<Transform> waitingPassengers;
    public List<Passenger> activePassengers;

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        PopulatePathData(20);
        startNode = Instantiate(nodePre, Vector3.right * 3, Quaternion.identity).transform;
        startNode.GetComponent<PathNode>().attachedSeats = new List<(Transform node, int id)>();
        Transform lastNode = startNode;
        foreach(var nodeData in pathData){
            PathNode lastNodeScript = lastNode.GetComponent<PathNode>();
            Transform currentNode = Instantiate(nodePre, nodeData.pos, Quaternion.identity).transform;
            lastNodeScript.nextNode = currentNode;
            PathNode currentNodeScript = currentNode.GetComponent<PathNode>();
            currentNodeScript.attachedSeats = new List<(Transform node, int id)>();
            if(nodeData.connectedSeats.Length > 0){
                Transform leftSeat = Instantiate(seatPre, nodeData.pos - Vector2.right * 2, Quaternion.identity).transform;
                leftSeat.GetComponent<SeatNode>().seatNumber = nodeData.connectedSeats[0];
                currentNodeScript.attachedSeats.Add((leftSeat, nodeData.connectedSeats[0]));
                if(nodeData.connectedSeats.Length > 1){
                    Transform rightSeat = Instantiate(seatPre, nodeData.pos + Vector2.right * 2, Quaternion.identity).transform;
                    rightSeat.GetComponent<SeatNode>().seatNumber = nodeData.connectedSeats[1];
                    currentNodeScript.attachedSeats.Add((rightSeat, nodeData.connectedSeats[1]));
                }
            }
            lastNode = currentNode;
        }
        StartCoroutine(RunSimulation(new int[] {20,18,16,14,12,10,8,6,4,2,19,17,15,13,11,9,7,5,3,1}));
    }

    void PopulatePathData(int planeSize)
    {
        pathData = new List<(Vector2 pos, int[] connectedSeats)>();
        pathData.Add((new Vector2(2, 0), new int[] {}));
        pathData.Add((new Vector2(1, 0), new int[] {}));
        pathData.Add((new Vector2(0, 0), new int[] {}));
        pathData.Add((new Vector2(0, 1), new int[] {}));
        for(int i = 1; i < planeSize + 1; i++){
            pathData.Add((new Vector2(0, i + 1), new int[] {2 * i - 1, 2 * i}));
        }
        tail.position = new Vector3(0, planeSize + 1.5f, 0);
        GameObject leftWing = Instantiate(wingPre, new Vector3(-3, planeSize / 2 + 2, 0), Quaternion.identity);
        leftWing.transform.localScale = Vector3.one * planeSize / 15;
        GameObject rightWing = Instantiate(wingPre, new Vector3(3, planeSize / 2 + 2, 0), Quaternion.Euler(0, 180, 0));
        rightWing.transform.localScale = Vector3.one * planeSize / 15;
    }

    void SpawnPassenger(int seat)
    {
        Transform passenger = Instantiate(passengerPre).transform;
        passenger.parent = queueNode;
        passenger.localPosition = Vector3.zero;
        Passenger passengerScript = passenger.GetComponent<Passenger>();
        passengerScript.assignedSeat = seat;
        waitingPassengers.Add(passenger);
        allPassengers.Add(passengerScript);
        passengerScript.active = false;
    }

    public IEnumerator RunSimulation(int[] passengerSequence)
    {
        allPassengers.Clear();
        for(int i = 0; i < passengerSequence.Length; i++){
            SpawnPassenger(passengerSequence[i]);
        }
        bool active = true;
        steps = 0;
        while(active){
            active = false;
            if(startNode.childCount == 0 && waitingPassengers.Count > 0){
                waitingPassengers[0].parent = startNode;
                waitingPassengers[0].GetComponent<Passenger>().active = true;
                activePassengers.Add(waitingPassengers[0].GetComponent<Passenger>());
                waitingPassengers.RemoveAt(0);
            }
            foreach(Passenger passenger in activePassengers){
                if(passenger.Tick()){
                    active = true;
                }
            }
            
            yield return new WaitForSeconds(0f);
            steps += 1;
            
        }
        //yield return new WaitForSeconds(0.1f);
        timePerPassenger = new int[allPassengers.Count];
        for(int i = 0; i < allPassengers.Count; i++){
            timePerPassenger[i] = allPassengers[i].time;
        }
        GameObject[] passengers = GameObject.FindGameObjectsWithTag("Passenger");
        for(int i = 0; i < passengers.Length; i++){
            Destroy(passengers[i]);
        }
    }

    public (int time, int[] timePerPassenger) GetScore()
    {
        return (steps, timePerPassenger);
    }
}

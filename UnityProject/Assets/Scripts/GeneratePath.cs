using UnityEngine;
using System.Collections;
using System.Collections.Generic;

public class GeneratePath : MonoBehaviour
{
    public GameObject nodePre;
    public GameObject seatPre;
    public GameObject passengerPre;
    public Transform startNode;
    public Transform queueNode;
    public List<(Vector2 pos, int[] connectedSeats)> pathData;
    public List<Transform> waitingPassengers;
    public List<Passenger> activePassengers;

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        PopulatePathData();
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
        StartCoroutine(RunSimulation());
    }

    void PopulatePathData()
    {
        pathData = new List<(Vector2 pos, int[] connectedSeats)>();
        pathData.Add((new Vector2(2, 0), new int[] {}));
        pathData.Add((new Vector2(1, 0), new int[] {}));
        pathData.Add((new Vector2(0, 0), new int[] {}));
        pathData.Add((new Vector2(0, 1), new int[] {}));
        for(int i = 1; i < 31; i++){
            pathData.Add((new Vector2(0, i + 1), new int[] {2 * i - 1, 2 * i}));
        }
    }

    void SpawnPassenger(int seat)
    {
        Transform passenger = Instantiate(passengerPre).transform;
        passenger.parent = queueNode;
        passenger.localPosition = Vector3.zero;
        Passenger passengerScript = passenger.GetComponent<Passenger>();
        passengerScript.assignedSeat = seat;
        waitingPassengers.Add(passenger);
        passengerScript.active = false;
    }

    public IEnumerator RunSimulation()
    {
        SpawnPassenger(1);
        SpawnPassenger(3);
        for(int i = 0; i < 120; i++){
            SpawnPassenger(Random.Range(1,60));
        }
        SpawnPassenger(4);
        while(true){
            foreach(Passenger passenger in activePassengers){
                passenger.Tick();
            }
            if(startNode.childCount == 0 && waitingPassengers.Count > 0){
                waitingPassengers[0].parent = startNode;
                waitingPassengers[0].GetComponent<Passenger>().active = true;
                activePassengers.Add(waitingPassengers[0].GetComponent<Passenger>());
                waitingPassengers.RemoveAt(0);
            }
            
            yield return new WaitForSeconds(0f);
            
        }
    }
}

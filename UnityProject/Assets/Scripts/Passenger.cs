using UnityEngine;
using TMPro;

public class Passenger : MonoBehaviour
{
    public int assignedSeat;
    public int busyTicks;
    public Transform target;
    public bool seated;
    public bool active;
    public int time;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        transform.GetChild(0).GetComponent<TextMeshPro>().text = assignedSeat.ToString();
    }

    void Update()
    {
        //Framerate dependent but it's fine we ball
        if(active){
            transform.localPosition /= 1.05f;
        }
    }

    // Update is called once per frame
    public bool Tick()
    {
        if(seated){
            return false;
        } else if(busyTicks == 0){
            time += 1;
            Transform currentNode = transform.parent;
            PathNode nodeScript = currentNode.GetComponent<PathNode>();
            foreach(var seat in nodeScript.attachedSeats){
                if(seat.id == assignedSeat){
                    busyTicks = 4;
                    target = seat.node;
                }
            }
            if(busyTicks == 0 && nodeScript.nextNode.childCount == 0){
                transform.parent = nodeScript.nextNode;
            }
        } else {
            busyTicks -= 1;
            if(busyTicks == 0){
                transform.parent = target;
                seated = true;
            }
        }
        //transform.localPosition = Vector3.zero;
        return true;
    }
}

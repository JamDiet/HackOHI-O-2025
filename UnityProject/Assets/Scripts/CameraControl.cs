using UnityEngine;

public class CameraControl : MonoBehaviour
{
    public Transform nose;
    public Transform tail;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        float scrollAxis = Input.GetAxis("Mouse ScrollWheel");
        transform.position += Vector3.up * scrollAxis;
        if(transform.position.y - 2 > tail.position.y){
            transform.position -= (transform.position - Vector3.up * 2 - new Vector3(0, tail.position.y, -10)) * Time.deltaTime * 5;
        } else if(transform.position.y + 2 < nose.position.y){
            transform.position -= (transform.position + Vector3.up * 2 - new Vector3(0, nose.position.y, -10)) * Time.deltaTime * 5;
        }
    }
}

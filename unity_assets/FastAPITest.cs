using UnityEngine;

public class FastAPITest : MonoBehaviour
{
    [Header("Test Options")]
    public bool testHealthOnStart = true;
    public bool testFullSessionUpload = false;

    private void Start()
    {
        if (testHealthOnStart)
        {
            Debug.Log("Checking Medical VR Backend status...");
            ApiClient.Instance.CheckServerStatus(OnHealthSuccess, OnHealthError);
        }

        if (testFullSessionUpload)
        {
            TestMockSession();
        }
    }

    private void OnHealthSuccess(ApiClient.BackendStatusResponse response)
    {
        Debug.Log("========================================");
        Debug.Log("✅ MEDICAL VR BACKEND CONNECTION SUCCESS!");
        Debug.Log("Status: " + response.status);
        Debug.Log("========================================");
    }

    private void OnHealthError(string error)
    {
        Debug.LogError("========================================");
        Debug.LogError("❌ BACKEND CONNECTION FAILED");
        Debug.LogError(error);
        Debug.LogError("Make sure backend is running: python3 run.py");
        Debug.LogError("========================================");
    }

    [ContextMenu("Test Full Session Upload")]
    public void TestMockSession()
    {
        Debug.Log("🧪 Starting mock session upload test...");

        SessionData mock = new SessionData
        {
            session_type = "TRAINING",
            session_number = 1,
            total_time_seconds = 120f
        };

        // Populate 16 steps
        for (int i = 0; i < 16; i++)
        {
            mock.steps.Add(new StepResult
            {
                step_id = i,
                step_name = "Step " + i,
                attempts = (i == 7) ? 2 : 1,
                mistakes = (i == 7) ? 1 : 0,
                first_attempt_correct = (i != 7),
                completed = true,
                step_time_seconds = 7.5f
            });
        }

        // Add 1 mistake on step 7
        mock.mistakes.Add(new MistakeResult
        {
            step_id = 7,
            mistake_type = "WRONG_OBJECT",
            attempt_number = 1
        });

        ApiClient.Instance.UploadSession(mock, (success, result) =>
        {
            if (success)
            {
                Debug.Log("🎉 Mock session successfully uploaded and graded!");
            }
            else
            {
                Debug.LogError("❌ Mock session upload failed: " + result);
            }
        });
    }
}

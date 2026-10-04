using System;
using System.Collections.Generic;
using UnityEngine;

public class SessionDataManager : MonoBehaviour
{
    public static SessionDataManager Instance;

    [Header("Session Configuration")]
    public int sessionNumber = 1;
    [Tooltip("TRAINING or TEST")]
    public string sessionType = "TRAINING";

    [Header("Export Options")]
    [Tooltip("Automatically request LLM clinical feedback after session completes")]
    public bool autoRequestAIFeedback = true;
    [Tooltip("Automatically download 2-page evaluation PDF locally")]
    public bool autoDownloadPDF = false;

    private SessionData sessionData;

    private Dictionary<int, StepResult> stepResults =
        new Dictionary<int, StepResult>();

    private List<MistakeResult> mistakes =
        new List<MistakeResult>();

    private float sessionStartTime;

    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }
        Instance = this;
    }

    private void Start()
    {
        sessionStartTime = Time.time;

        sessionData = new SessionData();
        sessionData.session_number = sessionNumber;
        sessionData.session_type = sessionType;

        Debug.Log("📦 Session Data Manager Started");
    }

    /// <summary>
    /// Call when a procedure step completes.
    /// </summary>
    public void RecordStep(
        int stepId,
        string stepName,
        int attempts,
        int mistakeCount,
        bool firstAttemptCorrect,
        bool completed,
        float completedAtSeconds,
        float stepTimeSeconds
    )
    {
        StepResult result = new StepResult();

        result.step_id = stepId;
        result.step_name = stepName;
        result.attempts = attempts;
        result.mistakes = mistakeCount;
        result.first_attempt_correct = firstAttemptCorrect;
        result.completed = completed;
        result.completed_at_seconds = completedAtSeconds;
        result.step_time_seconds = stepTimeSeconds;

        stepResults[stepId] = result;

        Debug.Log(
            $"📊 Step {stepId} ({stepName}) recorded | " +
            $"Attempts: {attempts} | " +
            $"Mistakes: {mistakeCount} | " +
            $"Time: {stepTimeSeconds:F2}s"
        );
    }

    /// <summary>
    /// Call when a clinical mistake occurs (WRONG_OBJECT, WRONG_ZONE, INCORRECT_PLACEMENT).
    /// </summary>
    public void RecordMistake(
        int stepId,
        string mistakeType,
        int attemptNumber
    )
    {
        MistakeResult mistake = new MistakeResult();

        mistake.step_id = stepId;
        mistake.mistake_type = mistakeType;
        mistake.attempt_number = attemptNumber;

        mistakes.Add(mistake);

        Debug.Log(
            $"❌ Mistake recorded | " +
            $"Step: {stepId} | " +
            $"Type: {mistakeType} | " +
            $"Attempt: {attemptNumber}"
        );
    }

    /// <summary>
    /// Compiles all steps and mistakes into a complete SessionData package.
    /// </summary>
    public SessionData BuildSessionData()
    {
        sessionData.steps.Clear();

        // Add steps in standardized procedure order: 0 -> 15
        for (int i = 0; i < 16; i++)
        {
            if (stepResults.ContainsKey(i))
            {
                sessionData.steps.Add(stepResults[i]);
            }
        }

        sessionData.mistakes = new List<MistakeResult>(mistakes);
        sessionData.total_time_seconds = Time.time - sessionStartTime;

        return sessionData;
    }

    /// <summary>
    /// Generates formatted JSON of the session.
    /// </summary>
    public string GenerateJSON()
    {
        SessionData data = BuildSessionData();
        string json = JsonUtility.ToJson(data, true);
        Debug.Log("📦 FINAL SESSION JSON:\n" + json);
        return json;
    }

    /// <summary>
    /// Exports and uploads the session to the Medical VR Backend via ApiClient.
    /// </summary>
    public void ExportSession(Action<bool, string> onComplete = null)
    {
        SessionData data = BuildSessionData();
        Debug.Log($"🚀 Uploading SessionData ({data.steps.Count} steps, {data.mistakes.Count} mistakes) to Backend...");

        if (ApiClient.Instance == null)
        {
            Debug.LogError("❌ ApiClient.Instance is null! Make sure an ApiClient GameObject is present in the scene.");
            onComplete?.Invoke(false, "ApiClient.Instance not found");
            return;
        }

        ApiClient.Instance.UploadSession(data, (success, msg) =>
        {
            if (success)
            {
                Debug.Log("✅ Session successfully uploaded and graded by backend!");

                int completedSessionId = ApiClient.Instance.activeSessionDbId;

                if (autoRequestAIFeedback && completedSessionId > 0)
                {
                    ApiClient.Instance.RequestAIEducationalFeedback(completedSessionId, "openbiollm", (aiSuccess, aiMsg) =>
                    {
                        if (aiSuccess)
                        {
                            Debug.Log("🤖 AI Clinical Feedback ready.");
                        }
                    });
                }

                if (autoDownloadPDF && completedSessionId > 0)
                {
                    string path = Application.persistentDataPath + $"/Report_Session_{completedSessionId}.pdf";
                    ApiClient.Instance.DownloadReportPdf(completedSessionId, path, (pdfSuccess, pdfPath) =>
                    {
                        if (pdfSuccess)
                        {
                            Debug.Log($"📄 PDF Report saved: {pdfPath}");
                        }
                    });
                }

                onComplete?.Invoke(true, msg);
            }
            else
            {
                Debug.LogError("❌ Session upload failed: " + msg);
                onComplete?.Invoke(false, msg);
            }
        });
    }
}

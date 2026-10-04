using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// Production-Ready Medical VR Backend Client for Unity (Venipuncture Simulation).
/// Attach this script to a persistent GameObject in your Unity scene or access via MedicalVRClient.Instance.
/// </summary>
public class MedicalVRClient : MonoBehaviour
{
    public static MedicalVRClient Instance { get; private set; }

    [Header("Server Configuration")]
    [Tooltip("Base URL of the Medical VR Backend")]
    public string serverBaseUrl = "http://127.0.0.1:8001";

    [Header("Active Session Telemetry")]
    public int activeUserId = -1;
    public int activeSessionDbId = -1;
    public string activeSessionCode = "";
    public string activeSessionType = "TEST"; // "TEST" or "TRAINING"

    private string jwtBearerToken = "";

    public bool IsAuthenticated => !string.IsNullOrEmpty(jwtBearerToken);

    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }
        Instance = this;
        DontDestroyOnLoad(gameObject);
    }

    #region 1. Authentication

    /// <summary>
    /// Authenticates a trainee using username (email) and password.
    /// </summary>
    public void Login(string email, string password, Action<bool, string> onComplete)
    {
        StartCoroutine(LoginRoutine(email, password, onComplete));
    }

    private IEnumerator LoginRoutine(string email, string password, Action<bool, string> onComplete)
    {
        string url = $"{serverBaseUrl}/api/auth/login";
        WWWForm form = new WWWForm();
        form.AddField("username", email);
        form.AddField("password", password);

        using (UnityWebRequest req = UnityWebRequest.Post(url, form))
        {
            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                AuthResponse res = JsonUtility.FromJson<AuthResponse>(req.downloadHandler.text);
                jwtBearerToken = res.access_token;
                activeUserId = res.user_id;
                Debug.Log($"[MedicalVR] Login successful for trainee: {res.name} (ID: {res.user_id})");
                onComplete?.Invoke(true, req.downloadHandler.text);
            }
            else
            {
                Debug.LogError($"[MedicalVR] Login error: {req.error} | {req.downloadHandler.text}");
                onComplete?.Invoke(false, req.error);
            }
        }
    }

    /// <summary>
    /// Refreshes the trainee's JWT bearer token during long VR simulations.
    /// </summary>
    public void RefreshToken(Action<bool> onComplete)
    {
        StartCoroutine(RefreshTokenRoutine(onComplete));
    }

    private IEnumerator RefreshTokenRoutine(Action<bool> onComplete)
    {
        string url = $"{serverBaseUrl}/api/auth/refresh";
        using (UnityWebRequest req = UnityWebRequest.PostWwwForm(url, ""))
        {
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);
            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                AuthResponse res = JsonUtility.FromJson<AuthResponse>(req.downloadHandler.text);
                jwtBearerToken = res.access_token;
                Debug.Log("[MedicalVR] Token refreshed successfully.");
                onComplete?.Invoke(true);
            }
            else
            {
                Debug.LogError($"[MedicalVR] Refresh token failed: {req.error}");
                onComplete?.Invoke(false);
            }
        }
    }

    #endregion

    #region 2. Session Lifecycle

    /// <summary>
    /// Starts a new TEST or TRAINING simulation session.
    /// </summary>
    public void StartSession(string sessionType, int sessionNumber, Action<bool, int> onComplete)
    {
        StartCoroutine(StartSessionRoutine(sessionType, sessionNumber, onComplete));
    }

    private IEnumerator StartSessionRoutine(string sessionType, int sessionNumber, Action<bool, int> onComplete)
    {
        string url = $"{serverBaseUrl}/api/sessions/";
        SessionCreatePayload payload = new SessionCreatePayload
        {
            user_id = activeUserId,
            session_type = sessionType,
            session_number = sessionNumber
        };

        string json = JsonUtility.ToJson(payload);
        using (UnityWebRequest req = new UnityWebRequest(url, "POST"))
        {
            byte[] bodyRaw = Encoding.UTF8.GetBytes(json);
            req.uploadHandler = new UploadHandlerRaw(bodyRaw);
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);

            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                SessionResponse res = JsonUtility.FromJson<SessionResponse>(req.downloadHandler.text);
                activeSessionDbId = res.id;
                activeSessionCode = res.session_id;
                activeSessionType = res.session_type;
                Debug.Log($"[MedicalVR] Active session started: {activeSessionCode} (DB ID: {activeSessionDbId})");
                onComplete?.Invoke(true, activeSessionDbId);
            }
            else
            {
                Debug.LogError($"[MedicalVR] Start session failed: {req.error} | {req.downloadHandler.text}");
                onComplete?.Invoke(false, -1);
            }
        }
    }

    /// <summary>
    /// Completes the active session and triggers authoritative assessment calculation.
    /// </summary>
    public void CompleteSession(Action<bool, string> onComplete)
    {
        StartCoroutine(CompleteSessionRoutine(onComplete));
    }

    private IEnumerator CompleteSessionRoutine(Action<bool, string> onComplete)
    {
        string url = $"{serverBaseUrl}/api/sessions/{activeSessionDbId}/complete";
        using (UnityWebRequest req = UnityWebRequest.PostWwwForm(url, ""))
        {
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);
            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                Debug.Log($"[MedicalVR] Session {activeSessionDbId} completed successfully.");
                onComplete?.Invoke(true, req.downloadHandler.text);
            }
            else
            {
                Debug.LogError($"[MedicalVR] Complete session failed: {req.error}");
                onComplete?.Invoke(false, req.error);
            }
        }
    }

    #endregion

    #region 3. Telemetry & Mistakes Logging

    /// <summary>
    /// Logs telemetry for a single procedure step (Steps 0 to 15).
    /// </summary>
    public void LogStepPerformance(int stepId, int attempts, int mistakes, bool firstAttemptCorrect, float stepTimeSeconds, bool completed, Action<bool> onComplete = null)
    {
        StartCoroutine(LogStepRoutine(stepId, attempts, mistakes, firstAttemptCorrect, stepTimeSeconds, completed, onComplete));
    }

    private IEnumerator LogStepRoutine(int stepId, int attempts, int mistakes, bool firstAttemptCorrect, float stepTimeSeconds, bool completed, Action<bool> onComplete)
    {
        string url = $"{serverBaseUrl}/api/step-performance/";
        StepPerformancePayload payload = new StepPerformancePayload
        {
            session_id = activeSessionDbId,
            step_id = stepId,
            attempts = attempts,
            mistakes = mistakes,
            first_attempt_correct = firstAttemptCorrect,
            step_time_seconds = stepTimeSeconds,
            completed = completed
        };

        string json = JsonUtility.ToJson(payload);
        using (UnityWebRequest req = new UnityWebRequest(url, "POST"))
        {
            req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);

            yield return req.SendWebRequest();
            onComplete?.Invoke(req.result == UnityWebRequest.Result.Success);
        }
    }

    /// <summary>
    /// Logs a clinical mistake (WRONG_OBJECT, WRONG_ZONE, INCORRECT_PLACEMENT).
    /// </summary>
    public void LogMistake(int stepId, string mistakeType, int attemptNumber, Action<bool> onComplete = null)
    {
        StartCoroutine(LogMistakeRoutine(stepId, mistakeType, attemptNumber, onComplete));
    }

    private IEnumerator LogMistakeRoutine(int stepId, string mistakeType, int attemptNumber, Action<bool> onComplete)
    {
        string url = $"{serverBaseUrl}/api/mistakes/";
        MistakePayload payload = new MistakePayload
        {
            session_id = activeSessionDbId,
            step_id = stepId,
            mistake_type = mistakeType,
            attempt_number = attemptNumber
        };

        string json = JsonUtility.ToJson(payload);
        using (UnityWebRequest req = new UnityWebRequest(url, "POST"))
        {
            req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);

            yield return req.SendWebRequest();
            onComplete?.Invoke(req.result == UnityWebRequest.Result.Success);
        }
    }

    /// <summary>
    /// Batches multiple step performance records in a single network upload.
    /// Recommended for network resiliency in VR headsets.
    /// </summary>
    public void LogBatchStepPerformance(List<StepPerformancePayload> batchSteps, Action<bool> onComplete = null)
    {
        StartCoroutine(LogBatchRoutine(batchSteps, onComplete));
    }

    private IEnumerator LogBatchRoutine(List<StepPerformancePayload> batchSteps, Action<bool> onComplete)
    {
        string url = $"{serverBaseUrl}/api/step-performance/batch";
        string json = JsonUtility.ToJson(new BatchWrapper { items = batchSteps });
        // Clean array wrapper for Unity JsonUtility
        string rawJson = json.Substring(9, json.Length - 10);

        using (UnityWebRequest req = new UnityWebRequest(url, "POST"))
        {
            req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(rawJson));
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);

            yield return req.SendWebRequest();
            onComplete?.Invoke(req.result == UnityWebRequest.Result.Success);
        }
    }

    #endregion

    #region 4. AI Feedback & PDF Report Download

    /// <summary>
    /// Requests grounded clinical AI feedback for the completed session.
    /// </summary>
    public void RequestAIEducationalFeedback(string modelName = "openbiollm", Action<bool, string> onComplete = null)
    {
        StartCoroutine(RequestAIFeedbackRoutine(modelName, onComplete));
    }

    private IEnumerator RequestAIFeedbackRoutine(string modelName, Action<bool, string> onComplete)
    {
        string url = $"{serverBaseUrl}/api/reports/{activeSessionDbId}/ai?model_name={modelName}";
        using (UnityWebRequest req = UnityWebRequest.PostWwwForm(url, ""))
        {
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);
            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                Debug.Log($"[MedicalVR] AI Feedback successfully received: {req.downloadHandler.text}");
                onComplete?.Invoke(true, req.downloadHandler.text);
            }
            else
            {
                Debug.LogError($"[MedicalVR] AI Feedback request failed: {req.error}");
                onComplete?.Invoke(false, req.error);
            }
        }
    }

    /// <summary>
    /// Downloads the official 2-page PDF evaluation report to local storage.
    /// </summary>
    public void DownloadReportPdf(string destinationPath, Action<bool, string> onComplete = null)
    {
        StartCoroutine(DownloadPdfRoutine(destinationPath, onComplete));
    }

    private IEnumerator DownloadPdfRoutine(string destinationPath, Action<bool, string> onComplete)
    {
        string url = $"{serverBaseUrl}/api/reports/{activeSessionDbId}/pdf";
        using (UnityWebRequest req = UnityWebRequest.Get(url))
        {
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);
            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                System.IO.File.WriteAllBytes(destinationPath, req.downloadHandler.data);
                Debug.Log($"[MedicalVR] PDF Report saved to: {destinationPath}");
                onComplete?.Invoke(true, destinationPath);
            }
            else
            {
                Debug.LogError($"[MedicalVR] Failed to download PDF: {req.error}");
                onComplete?.Invoke(false, req.error);
            }
        }
    }

    /// <summary>
    /// Downloads the official 5-page Longitudinal Trainee Clinical Portfolio PDF to local storage.
    /// Server strictly validates ownership: requested userId must match the authenticated JWT user.
    /// </summary>
    public void DownloadPortfolioPdf(int userId, string destinationPath, Action<bool, string> onComplete = null)
    {
        StartCoroutine(DownloadPortfolioPdfRoutine(userId, destinationPath, onComplete));
    }

    private IEnumerator DownloadPortfolioPdfRoutine(int userId, string destinationPath, Action<bool, string> onComplete)
    {
        string url = $"{serverBaseUrl}/api/users/{userId}/dashboard/pdf";
        using (UnityWebRequest req = UnityWebRequest.Get(url))
        {
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);
            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                System.IO.File.WriteAllBytes(destinationPath, req.downloadHandler.data);
                Debug.Log($"[MedicalVR] Portfolio PDF saved to: {destinationPath}");
                onComplete?.Invoke(true, destinationPath);
            }
            else
            {
                Debug.LogError($"[MedicalVR] Failed to download Portfolio PDF: {req.error} | {req.downloadHandler.text}");
                onComplete?.Invoke(false, req.error);
            }
        }
    }

    #endregion

    #region Data Transfer Objects (DTOs)

    [Serializable]
    public class AuthResponse
    {
        public string access_token;
        public string token_type;
        public int user_id;
        public string name;
        public string email;
    }

    [Serializable]
    public class SessionCreatePayload
    {
        public int user_id;
        public string session_type;
        public int session_number;
    }

    [Serializable]
    public class SessionResponse
    {
        public int id;
        public string session_id;
        public int user_id;
        public string session_type;
        public int session_number;
        public string status;
    }

    [Serializable]
    public class StepPerformancePayload
    {
        public int session_id;
        public int step_id;
        public int attempts;
        public int mistakes;
        public bool first_attempt_correct;
        public float step_time_seconds;
        public bool completed;
    }

    [Serializable]
    public class MistakePayload
    {
        public int session_id;
        public int step_id;
        public string mistake_type;
        public int attempt_number;
    }

    [Serializable]
    public class BatchWrapper
    {
        public List<StepPerformancePayload> items;
    }

    #endregion
}

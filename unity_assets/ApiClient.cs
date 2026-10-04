using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// ApiClient: Connects Unity VR simulation telemetry directly to the Medical VR Backend.
/// Handles Authentication (JWT), Session creation, Batch telemetry ingestion, Mistakes, and Report generation.
/// </summary>
public class ApiClient : MonoBehaviour
{
    public static ApiClient Instance;

    [Header("Backend Server Configuration")]
    [Tooltip("Base URL of the Medical VR Backend (Port 8001)")]
    [SerializeField]
    public string baseUrl = "http://127.0.0.1:8001";

    [Header("Default Trainee Credentials")]
    [SerializeField]
    public string defaultUsername = "trainee@hospital.org";
    [SerializeField]
    public string defaultPassword = "Password123!";

    [Header("Session State (Read Only)")]
    public int activeUserId = -1;
    public int activeSessionDbId = -1;
    public string activeSessionCode = "";
    public string jwtBearerToken = "";

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

    #region 1. Server Status & Health Check

    public void CheckServerStatus(Action<BackendStatusResponse> onSuccess, Action<string> onError)
    {
        StartCoroutine(GetStatusRoutine(onSuccess, onError));
    }

    private IEnumerator GetStatusRoutine(Action<BackendStatusResponse> onSuccess, Action<string> onError)
    {
        string url = baseUrl.TrimEnd('/') + "/health";

        using (UnityWebRequest req = UnityWebRequest.Get(url))
        {
            req.timeout = 10;
            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                Debug.Log("[ApiClient] Health check response: " + req.downloadHandler.text);
                try
                {
                    BackendStatusResponse response = JsonUtility.FromJson<BackendStatusResponse>(req.downloadHandler.text);
                    onSuccess?.Invoke(response);
                }
                catch (Exception e)
                {
                    onError?.Invoke("JSON parsing failed: " + e.Message);
                }
            }
            else
            {
                onError?.Invoke($"Backend connection failed ({url}): " + req.error);
            }
        }
    }

    #endregion

    #region 2. Trainee Authentication

    public void Login(string username, string password, Action<bool, string> onComplete = null)
    {
        StartCoroutine(LoginRoutine(username, password, onComplete));
    }

    private IEnumerator LoginRoutine(string username, string password, Action<bool, string> onComplete)
    {
        string url = baseUrl.TrimEnd('/') + "/api/auth/login";
        WWWForm form = new WWWForm();
        form.AddField("username", username);
        form.AddField("password", password);

        using (UnityWebRequest req = UnityWebRequest.Post(url, form))
        {
            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                AuthResponse res = JsonUtility.FromJson<AuthResponse>(req.downloadHandler.text);
                jwtBearerToken = res.access_token;
                activeUserId = res.user_id;
                Debug.Log($"[ApiClient] Logged in as: {res.name} (User ID: {res.user_id})");
                onComplete?.Invoke(true, req.downloadHandler.text);
            }
            else
            {
                Debug.LogError($"[ApiClient] Login failed: {req.error} | {req.downloadHandler.text}");
                onComplete?.Invoke(false, req.error);
            }
        }
    }

    #endregion

    #region 3. Full Session Upload Flow

    /// <summary>
    /// Uploads the entire SessionData object compiled by SessionDataManager:
    /// 1. Ensures authenticated (auto-logs in if needed)
    /// 2. Creates the session in the backend DB
    /// 3. Uploads all 16 step telemetry records in batch
    /// 4. Uploads all recorded mistakes
    /// 5. Completes session & triggers deterministic grading
    /// </summary>
    public void UploadSession(SessionData sessionData, Action<bool, string> onComplete = null)
    {
        StartCoroutine(UploadSessionRoutine(sessionData, onComplete));
    }

    private IEnumerator UploadSessionRoutine(SessionData sessionData, Action<bool, string> onComplete)
    {
        // A. Ensure Authenticated
        if (!IsAuthenticated)
        {
            Debug.Log("[ApiClient] Not logged in. Performing auto-login before upload...");
            bool loginSuccess = false;
            string loginError = "";

            yield return StartCoroutine(LoginRoutine(defaultUsername, defaultPassword, (ok, msg) =>
            {
                loginSuccess = ok;
                loginError = msg;
            }));

            if (!loginSuccess)
            {
                onComplete?.Invoke(false, "Authentication failed: " + loginError);
                yield break;
            }
        }

        // B. Create Session (POST /api/sessions/)
        string sessionUrl = baseUrl.TrimEnd('/') + "/api/sessions/";
        SessionCreatePayload sessPayload = new SessionCreatePayload
        {
            user_id = activeUserId,
            session_type = string.IsNullOrEmpty(sessionData.session_type) ? "TRAINING" : sessionData.session_type,
            session_number = sessionData.session_number > 0 ? sessionData.session_number : 1
        };

        int sessionDbId = -1;
        using (UnityWebRequest req = new UnityWebRequest(sessionUrl, "POST"))
        {
            byte[] body = Encoding.UTF8.GetBytes(JsonUtility.ToJson(sessPayload));
            req.uploadHandler = new UploadHandlerRaw(body);
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);

            yield return req.SendWebRequest();

            if (req.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError($"[ApiClient] Failed to create session: {req.error} | {req.downloadHandler.text}");
                onComplete?.Invoke(false, "Create session failed: " + req.error);
                yield break;
            }

            SessionResponse res = JsonUtility.FromJson<SessionResponse>(req.downloadHandler.text);
            sessionDbId = res.id;
            activeSessionDbId = sessionDbId;
            activeSessionCode = res.session_id;
            Debug.Log($"[ApiClient] Created Session DB ID: {sessionDbId} (UUID: {activeSessionCode})");
        }

        // C. Upload Batch Step Performance (POST /api/step-performance/batch)
        if (sessionData.steps != null && sessionData.steps.Count > 0)
        {
            string batchUrl = baseUrl.TrimEnd('/') + "/api/step-performance/batch";
            List<BackendStepPayload> backendSteps = new List<BackendStepPayload>();

            foreach (var s in sessionData.steps)
            {
                backendSteps.Add(new BackendStepPayload
                {
                    session_id = sessionDbId,
                    step_id = s.step_id,
                    attempts = s.attempts,
                    mistakes = s.mistakes,
                    first_attempt_correct = s.first_attempt_correct,
                    step_time_seconds = s.step_time_seconds,
                    completed = s.completed
                });
            }

            string batchJson = JsonUtility.ToJson(new StepBatchWrapper { items = backendSteps });
            // Unwrap from {"items": [...]} to raw JSON array [...] for FastAPI
            string rawBatchJson = batchJson.Substring(9, batchJson.Length - 10);

            using (UnityWebRequest req = new UnityWebRequest(batchUrl, "POST"))
            {
                req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(rawBatchJson));
                req.downloadHandler = new DownloadHandlerBuffer();
                req.SetRequestHeader("Content-Type", "application/json");
                req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);

                yield return req.SendWebRequest();

                if (req.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogError($"[ApiClient] Step batch upload failed: {req.error} | {req.downloadHandler.text}");
                }
                else
                {
                    Debug.Log($"[ApiClient] Successfully synced {backendSteps.Count} steps.");
                }
            }
        }

        // D. Upload Mistakes (POST /api/mistakes/)
        if (sessionData.mistakes != null && sessionData.mistakes.Count > 0)
        {
            string mistakeUrl = baseUrl.TrimEnd('/') + "/api/mistakes/";

            foreach (var m in sessionData.mistakes)
            {
                BackendMistakePayload mPayload = new BackendMistakePayload
                {
                    session_id = sessionDbId,
                    step_id = m.step_id,
                    mistake_type = m.mistake_type,
                    attempt_number = m.attempt_number
                };

                using (UnityWebRequest req = new UnityWebRequest(mistakeUrl, "POST"))
                {
                    req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(mPayload)));
                    req.downloadHandler = new DownloadHandlerBuffer();
                    req.SetRequestHeader("Content-Type", "application/json");
                    req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);

                    yield return req.SendWebRequest();

                    if (req.result != UnityWebRequest.Result.Success)
                    {
                        Debug.LogWarning($"[ApiClient] Mistake upload warning: {req.error} | {req.downloadHandler.text}");
                    }
                }
            }
            Debug.Log($"[ApiClient] Synced {sessionData.mistakes.Count} clinical mistakes.");
        }

        // E. Complete Session (POST /api/sessions/{session_id}/complete)
        string completeUrl = baseUrl.TrimEnd('/') + $"/api/sessions/{sessionDbId}/complete";
        using (UnityWebRequest req = UnityWebRequest.PostWwwForm(completeUrl, ""))
        {
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);
            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                Debug.Log($"[ApiClient] Session {sessionDbId} marked COMPLETED. Deterministic assessment finalized!");
                onComplete?.Invoke(true, req.downloadHandler.text);
            }
            else
            {
                Debug.LogError($"[ApiClient] Session completion failed: {req.error}");
                onComplete?.Invoke(false, req.error);
            }
        }
    }

    #endregion

    #region 4. AI Feedback & PDF Report Helpers

    public void RequestAIEducationalFeedback(int sessionDbId, string model = "openbiollm", Action<bool, string> onComplete = null)
    {
        StartCoroutine(RequestAIFeedbackRoutine(sessionDbId, model, onComplete));
    }

    private IEnumerator RequestAIFeedbackRoutine(int sessionDbId, string model, Action<bool, string> onComplete)
    {
        string url = baseUrl.TrimEnd('/') + $"/api/reports/{sessionDbId}/ai?model_name={model}";
        using (UnityWebRequest req = UnityWebRequest.PostWwwForm(url, ""))
        {
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);
            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                Debug.Log($"[ApiClient] AI Feedback generated: {req.downloadHandler.text}");
                onComplete?.Invoke(true, req.downloadHandler.text);
            }
            else
            {
                Debug.LogError($"[ApiClient] AI Feedback request failed: {req.error}");
                onComplete?.Invoke(false, req.error);
            }
        }
    }

    public void DownloadReportPdf(int sessionDbId, string destinationPath, Action<bool, string> onComplete = null)
    {
        StartCoroutine(DownloadReportPdfRoutine(sessionDbId, destinationPath, onComplete));
    }

    private IEnumerator DownloadReportPdfRoutine(int sessionDbId, string destinationPath, Action<bool, string> onComplete)
    {
        string url = baseUrl.TrimEnd('/') + $"/api/reports/{sessionDbId}/pdf";
        using (UnityWebRequest req = UnityWebRequest.Get(url))
        {
            req.SetRequestHeader("Authorization", "Bearer " + jwtBearerToken);
            yield return req.SendWebRequest();

            if (req.result == UnityWebRequest.Result.Success)
            {
                System.IO.File.WriteAllBytes(destinationPath, req.downloadHandler.data);
                Debug.Log($"[ApiClient] Report PDF saved to: {destinationPath}");
                onComplete?.Invoke(true, destinationPath);
            }
            else
            {
                Debug.LogError($"[ApiClient] PDF download failed: {req.error}");
                onComplete?.Invoke(false, req.error);
            }
        }
    }

    #endregion

    #region Internal DTOs

    [Serializable]
    public class BackendStatusResponse
    {
        public string status;
    }

    [Serializable]
    private class AuthResponse
    {
        public string access_token;
        public string token_type;
        public int user_id;
        public string name;
        public string email;
    }

    [Serializable]
    private class SessionCreatePayload
    {
        public int user_id;
        public string session_type;
        public int session_number;
    }

    [Serializable]
    private class SessionResponse
    {
        public int id;
        public string session_id;
        public int user_id;
        public string session_type;
        public int session_number;
        public string status;
    }

    [Serializable]
    private class BackendStepPayload
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
    private class BackendMistakePayload
    {
        public int session_id;
        public int step_id;
        public string mistake_type;
        public int attempt_number;
    }

    [Serializable]
    private class StepBatchWrapper
    {
        public List<BackendStepPayload> items;
    }

    #endregion
}

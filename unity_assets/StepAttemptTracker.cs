using System.Collections.Generic;
using UnityEngine;

[System.Serializable]
public class StepAttemptData
{
    public int step_id;
    public int attempts;
    public int mistakes;
    public bool first_attempt_correct;
    public float step_start_time;
    public float step_time_seconds;
    public List<string> mistake_types = new List<string>();
}

public class StepAttemptTracker : MonoBehaviour
{
    public static StepAttemptTracker Instance;

    private Dictionary<int, StepAttemptData> stepData =
        new Dictionary<int, StepAttemptData>();

    private int currentStep = -1;

    // Canonical 16-step venipuncture names
    private static readonly string[] StepNames = new string[]
    {
        "Wash Hands", "Wear Gloves", "Apply Tourniquet", "Take Cotton",
        "Dip Cotton in Spirit", "Clean Area", "Dispose Cotton", "Take Cannula",
        "Insert Cannula", "Remove Tourniquet", "Take Blood Collection Tube",
        "Insert Tube", "Blood Collection", "Remove Tube", "Remove Cannula", "Dispose Cannula"
    };

    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }
        Instance = this;
    }

    public void StartStep(int stepId)
    {
        currentStep = stepId;

        if (!stepData.ContainsKey(stepId))
        {
            StepAttemptData data = new StepAttemptData();
            data.step_id = stepId;
            data.attempts = 1; // Initial attempt begins
            data.mistakes = 0;
            data.first_attempt_correct = false;
            data.step_start_time = Time.time;
            stepData.Add(stepId, data);
        }
        else
        {
            stepData[stepId].step_start_time = Time.time;
        }

        Debug.Log($"🎯 Attempt tracking started for Step {stepId} ({GetStepName(stepId)})");
    }

    public void RecordAttempt()
    {
        if (currentStep < 0 || !stepData.ContainsKey(currentStep))
            return;

        StepAttemptData data = stepData[currentStep];
        data.attempts++;

        Debug.Log($"🔵 Step {currentStep} Attempt #{data.attempts}");
    }

    /// <summary>
    /// Records a clinical mistake (WRONG_OBJECT, WRONG_ZONE, INCORRECT_PLACEMENT).
    /// </summary>
    public void RecordMistake(string mistakeType)
    {
        if (currentStep < 0 || !stepData.ContainsKey(currentStep))
            return;

        StepAttemptData data = stepData[currentStep];
        data.mistakes++;
        data.mistake_types.Add(mistakeType);

        Debug.Log($"❌ Step {currentStep} Mistake: {mistakeType} (Total mistakes on this step: {data.mistakes})");

        // Forward to SessionDataManager if active
        if (SessionDataManager.Instance != null)
        {
            SessionDataManager.Instance.RecordMistake(currentStep, mistakeType, data.attempts);
        }
    }

    public void CompleteStepSuccessfully()
    {
        if (currentStep < 0 || !stepData.ContainsKey(currentStep))
            return;

        StepAttemptData data = stepData[currentStep];
        data.first_attempt_correct = (data.attempts <= 1 && data.mistakes == 0);
        data.step_time_seconds = Time.time - data.step_start_time;

        Debug.Log(
            $"✅ Step {currentStep} completed | " +
            $"Attempts: {data.attempts} | " +
            $"Mistakes: {data.mistakes} | " +
            $"First Attempt Correct: {data.first_attempt_correct} | " +
            $"Time: {data.step_time_seconds:F2}s"
        );

        // Forward to SessionDataManager
        if (SessionDataManager.Instance != null)
        {
            SessionDataManager.Instance.RecordStep(
                stepId: currentStep,
                stepName: GetStepName(currentStep),
                attempts: data.attempts,
                mistakeCount: data.mistakes,
                firstAttemptCorrect: data.first_attempt_correct,
                completed: true,
                completedAtSeconds: Time.time,
                stepTimeSeconds: data.step_time_seconds
            );
        }
    }

    private string GetStepName(int stepId)
    {
        if (stepId >= 0 && stepId < StepNames.Length)
            return StepNames[stepId];
        return $"Step {stepId}";
    }

    public StepAttemptData GetStepData(int stepId)
    {
        if (stepData.ContainsKey(stepId))
            return stepData[stepId];
        return null;
    }

    public int GetAttempts(int stepId)
    {
        StepAttemptData data = GetStepData(stepId);
        return data != null ? data.attempts : 0;
    }

    public int GetMistakes(int stepId)
    {
        StepAttemptData data = GetStepData(stepId);
        return data != null ? data.mistakes : 0;
    }

    public bool IsFirstAttemptCorrect(int stepId)
    {
        StepAttemptData data = GetStepData(stepId);
        return data != null && data.first_attempt_correct;
    }
}

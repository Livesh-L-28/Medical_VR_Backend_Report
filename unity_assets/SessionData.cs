using System;
using System.Collections.Generic;

[Serializable]
public class StepResult
{
    public int step_id;
    public string step_name;
    public int attempts;
    public int mistakes;
    public bool first_attempt_correct;
    public bool completed;
    public float completed_at_seconds;
    public float step_time_seconds;
}

[Serializable]
public class MistakeResult
{
    public int step_id;
    public string mistake_type;
    public int attempt_number;
}

[Serializable]
public class SessionData
{
    public int session_id;
    public string session_type = "TRAINING"; // "TRAINING" or "TEST"
    public int session_number = 1;
    public float total_time_seconds;

    public List<StepResult> steps = new List<StepResult>();
    public List<MistakeResult> mistakes = new List<MistakeResult>();
}

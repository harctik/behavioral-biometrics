# CHAPTER 3: SYSTEM DESIGN — TECHNICAL DIAGRAMS

### Studvisor Academic & AI-Assisted Advising Platform

---

## 3.3 Figure 3.1: Use-Case Diagram — Studvisor Platform (Landscape Unified Layout)

<div align="center">

<img src="https://mermaid.ink/svg/eyJjb2RlIjogImZsb3djaGFydCBMUlxuICAgIFMoKFwiU3R1ZGVudFwiKSlcbiAgICBcbiAgICBzdWJncmFwaCBTUFtcIlNUVURWSVNPUiBQTEFURk9STSBCT1VOREFSWVwiXVxuICAgICAgICBzdWJncmFwaCBTX1VDW1wiU3R1ZGVudCBTZXJ2aWNlc1wiXVxuICAgICAgICAgICAgVTFbVmlldyBQcm9maWxlXVxuICAgICAgICAgICAgVTJbQUkgVHV0b3JdXG4gICAgICAgICAgICBVM1tNb25pdG9yIE1hcmtzXVxuICAgICAgICAgICAgVTRbQ2FtcHVzIFdhbGxdXG4gICAgICAgICAgICBVNVtMZWF2ZSBSZXF1ZXN0XVxuICAgICAgICBlbmRcbiAgICAgICAgc3ViZ3JhcGggRl9VQ1tcIlN0YWZmICYgQWRtaW4gU2VydmljZXNcIl1cbiAgICAgICAgICAgIFU2W01hbmFnZSBBdHRlbmRhbmNlXVxuICAgICAgICAgICAgVTdbSW5wdXQgTWFya3NdXG4gICAgICAgICAgICBVOFtSaXNrIFNpZ25hbHNdXG4gICAgICAgICAgICBVOVtSZXBvcnRzXVxuICAgICAgICAgICAgVTEwW01hc3RlciBEYXRhXVxuICAgICAgICBlbmRcbiAgICBlbmRcbiAgICBcbiAgICBGKChcIkZhY3VsdHlcIikpXG4gICAgQSgoXCJBZG1pblwiKSlcblxuICAgIFMtLS1VMVxuICAgIFMtLS1VMlxuICAgIFMtLS1VM1xuICAgIFMtLS1VNFxuICAgIFMtLS1VNVxuXG4gICAgVTYtLS1GXG4gICAgVTctLS1GXG4gICAgVTgtLS1GXG4gICAgVTktLS1GXG5cbiAgICBVOC0tLUFcbiAgICBVOS0tLUFcbiAgICBVMTAtLS1BIiwgIm1lcm1haWQiOiB7InRoZW1lIjogImJhc2UiLCAidGhlbWVWYXJpYWJsZXMiOiB7InByaW1hcnlDb2xvciI6ICIjZmZmZmZmIiwgInByaW1hcnlUZXh0Q29sb3IiOiAiIzAwMDAwMCIsICJwcmltYXJ5Qm9yZGVyQ29sb3IiOiAiIzAwMDAwMCIsICJsaW5lQ29sb3IiOiAiIzAwMDAwMCIsICJzZWNvbmRhcnlDb2xvciI6ICIjZmZmZmZmIiwgInRlcnRpYXJ5Q29sb3IiOiAiI2ZmZmZmZiIsICJmb250U2l6ZSI6ICIxMnB4In19fQ" alt="Use-Case Diagram" style="max-width: 100%; max-height: 180mm; border: 1px solid #ddd; padding: 10px; background: white;" />

</div>

<details>
<summary><b>Click to show/hide raw Mermaid source code</b></summary>

```mermaid
flowchart LR
    S(("Student"))
    
    subgraph SP["STUDVISOR PLATFORM BOUNDARY"]
        subgraph S_UC["Student Services"]
            U1[View Profile]
            U2[AI Tutor]
            U3[Monitor Marks]
            U4[Campus Wall]
            U5[Leave Request]
        end
        subgraph F_UC["Staff & Admin Services"]
            U6[Manage Attendance]
            U7[Input Marks]
            U8[Risk Signals]
            U9[Reports]
            U10[Master Data]
        end
    end
    
    F(("Faculty"))
    A(("Admin"))

    S---U1
    S---U2
    S---U3
    S---U4
    S---U5

    U6---F
    U7---F
    U8---F
    U9---F

    U8---A
    U9---A
    U10---A
```

</details>

**Actors & Use Cases:**
- **Student (Primary User):** Views academic profiles, interacts with the AI Tutor via contextual chat, monitors attendance and marks in real-time, participates in the Campus Wall, and submits leave applications.
- **Faculty Member / HOD:** Manages classroom attendance with a 24-hour amendment window, inputs and updates internal marks, views AI-generated student risk signals, and generates class-level performance reports.
- **Administrator:** Manages institutional master data, oversees the append-only audit log, configures and monitors the AI engine, and accesses campus analytics dashboards.

---

## 3.4 Figure 3.2: Entity-Relationship Diagram — Studvisor Database Schema

<div align="center">

<img src="https://mermaid.ink/svg/eyJjb2RlIjogImVyRGlhZ3JhbVxuICAgIFVTRVJTIHtcbiAgICAgICAgaW50IHVzZXJfaWQgUEtcbiAgICAgICAgdmFyY2hhciB1c2VybmFtZVxuICAgICAgICB2YXJjaGFyIGVtYWlsXG4gICAgICAgIHZhcmNoYXIgcGFzc3dvcmRfaGFzaFxuICAgICAgICBlbnVtIHJvbGVcbiAgICAgICAgYm9vbCBpc19hY3RpdmVcbiAgICB9XG4gICAgU1RVREVOVFMge1xuICAgICAgICBpbnQgc3R1ZGVudF9pZCBQS1xuICAgICAgICBpbnQgdXNlcl9pZCBGS1xuICAgICAgICB2YXJjaGFyIGJhdGNoXG4gICAgICAgIGludCBzZW1lc3RlclxuICAgICAgICBmbG9hdCBjZ3BhXG4gICAgfVxuICAgIEZBQ1VMVFkge1xuICAgICAgICBpbnQgZmFjdWx0eV9pZCBQS1xuICAgICAgICBpbnQgdXNlcl9pZCBGS1xuICAgICAgICB2YXJjaGFyIGVtcF9jb2RlXG4gICAgICAgIHZhcmNoYXIgZGVzaWduYXRpb25cbiAgICB9XG4gICAgQVRURU5EQU5DRSB7XG4gICAgICAgIGludCByZWNvcmRfaWQgUEtcbiAgICAgICAgaW50IHN0dWRlbnRfaWQgRktcbiAgICAgICAgaW50IHN1YmplY3RfaWQgRktcbiAgICAgICAgZGF0ZSBkYXRlXG4gICAgICAgIGVudW0gc3RhdHVzXG4gICAgICAgIGludCBtYXJrZWRfYnkgRktcbiAgICB9XG4gICAgTUFSS1Mge1xuICAgICAgICBpbnQgbWFya19pZCBQS1xuICAgICAgICBpbnQgc3R1ZGVudF9pZCBGS1xuICAgICAgICBpbnQgc3ViamVjdF9pZCBGS1xuICAgICAgICB2YXJjaGFyIGNvbXBvbmVudFxuICAgICAgICBmbG9hdCBzY29yZVxuICAgICAgICBmbG9hdCBtYXhfc2NvcmVcbiAgICB9XG4gICAgTUVSSVRfTE9HIHtcbiAgICAgICAgaW50IGxvZ19pZCBQS1xuICAgICAgICBpbnQgc3R1ZGVudF9pZCBGS1xuICAgICAgICB2YXJjaGFyIGV2ZW50X3R5cGVcbiAgICAgICAgaW50IHhwX2RlbHRhXG4gICAgfVxuICAgIEFVRElUX0xPR1Mge1xuICAgICAgICBpbnQgbG9nX2lkIFBLXG4gICAgICAgIGludCBhY3Rvcl9pZCBGS1xuICAgICAgICB2YXJjaGFyIGFjdGlvblxuICAgICAgICBqc29uIHBheWxvYWRcbiAgICAgICAgdGltZXN0YW1wIHRzXG4gICAgfVxuICAgIFRJTUVUQUJMRSB7XG4gICAgICAgIGludCBzbG90X2lkIFBLXG4gICAgICAgIGludCBmYWN1bHR5X2lkIEZLXG4gICAgICAgIGludCBzdWJqZWN0X2lkIEZLXG4gICAgICAgIGludCByb29tX2lkIEZLXG4gICAgICAgIGludCBkYXlcbiAgICB9XG4gICAgQ0FNUFVTX1dBTEwge1xuICAgICAgICBpbnQgcG9zdF9pZCBQS1xuICAgICAgICB2YXJjaGFyIGhtYWNcbiAgICAgICAgdGV4dCBjb250ZW50XG4gICAgICAgIHZhcmNoYXIgc2VudGltZW50XG4gICAgICAgIGJvb2wgZXNjYWxhdGVkXG4gICAgfVxuICAgIFVTRVJTIHx8LS18fCBTVFVERU5UUyA6IFwiZXh0ZW5kc1wiXG4gICAgVVNFUlMgfHwtLXx8IEZBQ1VMVFkgOiBcImV4dGVuZHNcIlxuICAgIFNUVURFTlRTIHx8LS1veyBBVFRFTkRBTkNFIDogXCJoYXNcIlxuICAgIFNUVURFTlRTIHx8LS1veyBNQVJLUyA6IFwiZWFybnNcIlxuICAgIFNUVURFTlRTIHx8LS1veyBNRVJJVF9MT0cgOiBcImFjY3J1ZXNcIlxuICAgIEZBQ1VMVFkgfHwtLW97IFRJTUVUQUJMRSA6IFwidGVhY2hlc1wiXG4gICAgRkFDVUxUWSB8fC0tb3sgQVRURU5EQU5DRSA6IFwibWFya3NcIlxuICAgIFVTRVJTIHx8LS1veyBBVURJVF9MT0dTIDogXCJsb2dzXCIiLCAibWVybWFpZCI6IHsidGhlbWUiOiAiYmFzZSIsICJ0aGVtZVZhcmlhYmxlcyI6IHsicHJpbWFyeUNvbG9yIjogIiNmZmZmZmYiLCAicHJpbWFyeVRleHRDb2xvciI6ICIjMDAwMDAwIiwgInByaW1hcnlCb3JkZXJDb2xvciI6ICIjMDAwMDAwIiwgImxpbmVDb2xvciI6ICIjMDAwMDAwIiwgInNlY29uZGFyeUNvbG9yIjogIiNmZmZmZmYiLCAidGVydGlhcnlDb2xvciI6ICIjZmZmZmZmIiwgImZvbnRTaXplIjogIjEycHgifX19" alt="Entity Relationship Diagram" style="max-width: 100%; max-height: 180mm; border: 1px solid #ddd; padding: 10px; background: white;" />

</div>

<details>
<summary><b>Click to show/hide raw Mermaid source code</b></summary>

```mermaid
erDiagram
    USERS {
        int user_id PK
        varchar username
        varchar email
        varchar password_hash
        enum role
        bool is_active
    }
    STUDENTS {
        int student_id PK
        int user_id FK
        varchar batch
        int semester
        float cgpa
    }
    FACULTY {
        int faculty_id PK
        int user_id FK
        varchar emp_code
        varchar designation
    }
    ATTENDANCE {
        int record_id PK
        int student_id FK
        int subject_id FK
        date date
        enum status
        int marked_by FK
    }
    MARKS {
        int mark_id PK
        int student_id FK
        int subject_id FK
        varchar component
        float score
        float max_score
    }
    MERIT_LOG {
        int log_id PK
        int student_id FK
        varchar event_type
        int xp_delta
    }
    AUDIT_LOGS {
        int log_id PK
        int actor_id FK
        varchar action
        json payload
        timestamp ts
    }
    TIMETABLE {
        int slot_id PK
        int faculty_id FK
        int subject_id FK
        int room_id FK
        int day
    }
    CAMPUS_WALL {
        int post_id PK
        varchar hmac
        text content
        varchar sentiment
        bool escalated
    }
    USERS ||--|| STUDENTS : "extends"
    USERS ||--|| FACULTY : "extends"
    STUDENTS ||--o{ ATTENDANCE : "has"
    STUDENTS ||--o{ MARKS : "earns"
    STUDENTS ||--o{ MERIT_LOG : "accrues"
    FACULTY ||--o{ TIMETABLE : "teaches"
    FACULTY ||--o{ ATTENDANCE : "marks"
    USERS ||--o{ AUDIT_LOGS : "logs"
```

</details>

**Schema Summary:**
- **Core Identity (RBAC):** `users` maps 1:1 to `students` and `faculty` via polymorphic extension.
- **Academic Subsystem:** `attendance` and `marks` store per-student, per-subject records with faculty audit trails.
- **Gamification:** `merit_log` tracks XP deltas, badge acquisitions, and tier transitions.
- **Campus Wall:** `campus_wall` stores HMAC-anonymised content with rotating daily salts and sentiment labels.
- **Compliance:** `audit_logs` is an immutable, append-only table (INSERT-only permissions) capturing every state-changing operation.

---

## 3.5.1 Figure 3.3: DFD Level 0 — Context Diagram

<div align="center">

<img src="https://mermaid.ink/svg/eyJjb2RlIjogImZsb3djaGFydCBUQlxuICAgIFNbXCJTVFVERU5UXCJdXG4gICAgRltcIkZBQ1VMVFlcIl1cbiAgICBBW1wiQURNSU5cIl1cbiAgICBFW1wiRVhULiBBSSBQUk9WSURFUlwiXVxuICAgIEMoKFwiMC4wXG5TVFVEVklTT1JcblBMQVRGT1JNXCIpKVxuICAgIFMtLVwiQ3JlZGVudGlhbHMsIFF1ZXJpZXMsXG5MZWF2ZSwgV2FsbCBQb3N0c1wiLS0-Q1xuICAgIEMtLVwiQXR0ZW5kYW5jZSwgTWFya3MsXG5HUEEsIEFJIFN0cmVhbVwiLS0-U1xuICAgIEYtLVwiTWFya3MsIEF0dGVuZGFuY2UsXG5UaW1ldGFibGUgQ29uZmlnXCItLT5DXG4gICAgQy0tXCJSZXBvcnRzLFxuUmlzayBTaWduYWxzXCItLT5GXG4gICAgQS0tXCJNYXN0ZXIgQ29uZmlnLFxuUHJpdmFjeSBSdWxlc1wiLS0-Q1xuICAgIEMtLVwiQXVkaXQgRXhwb3J0cyxcbkFuYWx5dGljc1wiLS0-QVxuICAgIEMtLVwiU2FuaXRpc2VkIFByb21wdFwiLS0-RVxuICAgIEUtLVwiVG9rZW4gU3RyZWFtXCItLT5DIiwgIm1lcm1haWQiOiB7InRoZW1lIjogImJhc2UiLCAidGhlbWVWYXJpYWJsZXMiOiB7InByaW1hcnlDb2xvciI6ICIjZmZmZmZmIiwgInByaW1hcnlUZXh0Q29sb3IiOiAiIzAwMDAwMCIsICJwcmltYXJ5Qm9yZGVyQ29sb3IiOiAiIzAwMDAwMCIsICJsaW5lQ29sb3IiOiAiIzAwMDAwMCIsICJzZWNvbmRhcnlDb2xvciI6ICIjZmZmZmZmIiwgInRlcnRpYXJ5Q29sb3IiOiAiI2ZmZmZmZiIsICJmb250U2l6ZSI6ICIxMnB4In19fQ" alt="DFD Level 0" style="max-width: 100%; max-height: 180mm; border: 1px solid #ddd; padding: 10px; background: white;" />

</div>

<details>
<summary><b>Click to show/hide raw Mermaid source code</b></summary>

```mermaid
flowchart TB
    S["STUDENT"]
    F["FACULTY"]
    A["ADMIN"]
    E["EXT. AI PROVIDER"]
    C(("0.0
STUDVISOR
PLATFORM"))
    S--"Credentials, Queries,
Leave, Wall Posts"-->C
    C--"Attendance, Marks,
GPA, AI Stream"-->S
    F--"Marks, Attendance,
Timetable Config"-->C
    C--"Reports,
Risk Signals"-->F
    A--"Master Config,
Privacy Rules"-->C
    C--"Audit Exports,
Analytics"-->A
    C--"Sanitised Prompt"-->E
    E--"Token Stream"-->C
```

</details>

**Context-Level Data Flows:**
- **Student ↔ System:** Submits authentication credentials, academic queries, leave requests, and campus wall posts. Receives attendance logs, marks, GPA roll-ups, AI tutor streaming responses, and social merit updates.
- **Faculty ↔ System:** Inputs timetable settings and marks/attendance entries. Receives aggregate class metrics and student at-risk warnings.
- **Administrator ↔ System:** Feeds master configurations, security parameters, and privacy rule-sets. Retrieves append-only audit files and cohort-level analytics.
- **External AI Provider ↔ System:** Receives sanitised prompt payloads. Returns raw generated token streams.

---

## 3.5.2 Figure 3.4: DFD Level 1 — Major Backend Flows

<div align="center">

<img src="https://mermaid.ink/svg/eyJjb2RlIjogImZsb3djaGFydCBUQlxuICAgIFNbXCJTVFVERU5UXCJdXG4gICAgRltcIkZBQ1VMVFlcIl1cbiAgICBBW1wiQURNSU5cIl1cbiAgICBYW1wiRVhULiBBSVwiXVxuICAgIFAxKChcIlAxIEF1dGhcIikpXG4gICAgUDIoKFwiUDIgQWNhZGVtaWNcIikpXG4gICAgUDMoKFwiUDMgQUkgVHV0b3JcIikpXG4gICAgUDQoKFwiUDQgUmlza1wiKSlcbiAgICBQNSgoXCJQNSBXYWxsXCIpKVxuICAgIFA2KChcIlA2IE1lcml0XCIpKVxuICAgIFA3KChcIlA3IEF1ZGl0XCIpKVxuICAgIEQxWyhcIkQxIEFjYWRlbWljXCIpXVxuICAgIEQyWyhcIkQyIFdhbGxcIildXG4gICAgRDNbKFwiRDMgUmlza1wiKV1cbiAgICBENFsoXCJENCBNZXJpdFwiKV1cbiAgICBENVsoXCJENSBBdWRpdFwiKV1cbiAgICBTLS1cImNyZWRzXCItLT5QMVxuICAgIFAxLS1cIkpXVFwiLS0-U1xuICAgIEYtLVwibWFya3NcIi0tPlAyXG4gICAgUDItLT5EMVxuICAgIFAyLS0-UDZcbiAgICBTLS1cInF1ZXJ5XCItLT5QM1xuICAgIEQxLS0-UDNcbiAgICBQMy0tXCJwcm9tcHRcIi0tPlhcbiAgICBYLS1cInJlc3BcIi0tPlAzXG4gICAgUDMtLVwic3RyZWFtXCItLT5TXG4gICAgRDEtLT5QNFxuICAgIFA0LS0-RDNcbiAgICBEMy0tXCJmbGFnc1wiLS0-RlxuICAgIFMtLVwicG9zdFwiLS0-UDVcbiAgICBQNS0tPkQyXG4gICAgUDUtLVwiYWxlcnRcIi0tPkFcbiAgICBQNi0tPkQ0XG4gICAgRDQtLT5TXG4gICAgUDEtLi0-UDdcbiAgICBQMi0uLT5QN1xuICAgIFA1LS4tPlA3XG4gICAgUDctLT5ENVxuICAgIEQ1LS1cImV4cG9ydFwiLS0-QSIsICJtZXJtYWlkIjogeyJ0aGVtZSI6ICJiYXNlIiwgInRoZW1lVmFyaWFibGVzIjogeyJwcmltYXJ5Q29sb3IiOiAiI2ZmZmZmZiIsICJwcmltYXJ5VGV4dENvbG9yIjogIiMwMDAwMDAiLCAicHJpbWFyeUJvcmRlckNvbG9yIjogIiMwMDAwMDAiLCAibGluZUNvbG9yIjogIiMwMDAwMDAiLCAic2Vjb25kYXJ5Q29sb3IiOiAiI2ZmZmZmZiIsICJ0ZXJ0aWFyeUNvbG9yIjogIiNmZmZmZmYiLCAiZm9udFNpemUiOiAiMTJweCJ9fX0" alt="DFD Level 1" style="max-width: 100%; max-height: 180mm; border: 1px solid #ddd; padding: 10px; background: white;" />

</div>

<details>
<summary><b>Click to show/hide raw Mermaid source code</b></summary>

```mermaid
flowchart TB
    S["STUDENT"]
    F["FACULTY"]
    A["ADMIN"]
    X["EXT. AI"]
    P1(("P1 Auth"))
    P2(("P2 Academic"))
    P3(("P3 AI Tutor"))
    P4(("P4 Risk"))
    P5(("P5 Wall"))
    P6(("P6 Merit"))
    P7(("P7 Audit"))
    D1[("D1 Academic")]
    D2[("D2 Wall")]
    D3[("D3 Risk")]
    D4[("D4 Merit")]
    D5[("D5 Audit")]
    S--"creds"-->P1
    P1--"JWT"-->S
    F--"marks"-->P2
    P2-->D1
    P2-->P6
    S--"query"-->P3
    D1-->P3
    P3--"prompt"-->X
    X--"resp"-->P3
    P3--"stream"-->S
    D1-->P4
    P4-->D3
    D3--"flags"-->F
    S--"post"-->P5
    P5-->D2
    P5--"alert"-->A
    P6-->D4
    D4-->S
    P1-.->P7
    P2-.->P7
    P5-.->P7
    P7-->D5
    D5--"export"-->A
```

</details>

The Level 1 Data Flow Diagram (DFD) maps the major backend operations of the Studvisor platform by breaking down the central orchestrator into seven key processes (P1 through P7). Users interact with these processes using specific secure credentials, which are verified by Process P1 to distribute JWT tokens and establish safe sessions. Core academic entries such as attendance data, marks, and timetable updates are managed through Process P2 and stored permanently within Data Store D1. Process P3 acts as the AI tutoring engine, extracting profile context from Data Store D1 to generate grounded queries for the external LLM provider. Predictive computation occurs in Process P4, which scans grade and attendance trends to write at-risk flags to Data Store D3 and alert faculty members in real time. Finally, Processes P5 and P6 handle anonymous campus wall contributions and student gamification merits respectively, while Process P7 writes immutable state-change records to Data Store D5 for comprehensive audit compliance.

**Process Summary (P1–P7):**

| Process | Input Data Flows | Output Data Flows |
|:--------|:-----------------|:------------------|
| **P1: User Authentication** | username, password, device_fingerprint | JWT access + refresh tokens; Auth event → audit_logs |
| **P2: Academic Data Management** | Attendance, marks, timetable from Faculty | Updated records → D1; Risk signal recalculation triggered |
| **P3: AI Tutor Interaction** | student_id, session_id, query_text | Sanitised prompt → AI Provider; SSE stream → Student |
| **P4: Predictive Risk Computation** | Attendance slope, grade trend from D1 | Risk scores → D3; At-risk flags → Faculty dashboard |
| **P5: Campus Wall Processing** | Post submission, reactions | HMAC-tagged post → D2; Escalation → Admin alert queue |
| **P6: Merit & Gamification** | Academic actions | XP delta → D4; Badge events → Campus Wall widget |
| **P7: Audit & Compliance** | State-changing requests intercepted | Append-only record → D5; Admin audit export |

---

## 3.5.3 Figure 3.5: DFD Level 2 — AI Tutoring Sub-Process (P3)

<div align="center">

<img src="https://mermaid.ink/svg/eyJjb2RlIjogImZsb3djaGFydCBURFxuICAgIHN1YmdyYXBoIElOR1JFU1MgW1wiMS4gUXVlcnkgUmVjZXB0aW9uICYgQ29udGV4dCBHYXRoZXJpbmdcIl1cbiAgICAgICAgQ0xbXCJTdHVkZW50IENsaWVudFwiXVxuICAgICAgICBTU1soXCJTZXNzaW9uIFN0b3JlXCIpXVxuICAgICAgICBQMVtcIlAzLjEgUXVlcnlcblJlY2VwdGlvblwiXVxuICAgICAgICBQMltcIlAzLjIgQ29udGV4dFxuSW5qZWN0aW9uXCJdXG4gICAgICAgIEFEWyhcIkFjYWRlbWljIERCXCIpXVxuICAgIGVuZFxuICAgIFxuICAgIHN1YmdyYXBoIFJBR19MTE0gW1wiMi4gUkFHIFJldHJpZXZhbCAmIExMTSBQaXBlbGluZVwiXVxuICAgICAgICBQM1tcIlAzLjMgUkFHXG5SZXRyaWV2YWxcIl1cbiAgICAgICAgRklbKFwiRkFJU1MgSW5kZXhcIildXG4gICAgICAgIFA0W1wiUDMuNCBQSUlcblJlZGFjdGlvblwiXVxuICAgICAgICBMTVtcIkV4dGVybmFsIExMTVwiXVxuICAgICAgICBQNVtcIlAzLjUgUmVzcG9uc2VcblN0cmVhbWluZ1wiXVxuICAgIGVuZFxuXG4gICAgQ0wgLS1cInF1ZXJ5XCItLT4gUDFcbiAgICBTUyAtLVwiaGlzdG9yeVwiLS0-IFAxXG4gICAgUDEgLS0-IFAyXG4gICAgQUQgLS1cImRhdGFcIi0tPiBQMlxuICAgIFAyIC0tPiBQM1xuICAgIEZJIC0tXCJwYXNzYWdlc1wiLS0-IFAzXG4gICAgUDMgLS0-IFA0XG4gICAgUDQgLS0-IExNXG4gICAgTE0gLS0-IFA1XG4gICAgUDUgLS1cInN0cmVhbVwiLS0-IENMXG4gICAgUDUgLS1cInNhdmVcIi0tPiBTUyIsICJtZXJtYWlkIjogeyJ0aGVtZSI6ICJiYXNlIiwgInRoZW1lVmFyaWFibGVzIjogeyJwcmltYXJ5Q29sb3IiOiAiI2ZmZmZmZiIsICJwcmltYXJ5VGV4dENvbG9yIjogIiMwMDAwMDAiLCAicHJpbWFyeUJvcmRlckNvbG9yIjogIiMwMDAwMDAiLCAibGluZUNvbG9yIjogIiMwMDAwMDAiLCAic2Vjb25kYXJ5Q29sb3IiOiAiI2ZmZmZmZiIsICJ0ZXJ0aWFyeUNvbG9yIjogIiNmZmZmZmYiLCAiZm9udFNpemUiOiAiMTJweCJ9fX0" alt="DFD Level 2" style="max-width: 100%; max-height: 200mm; border: 1px solid #ddd; padding: 10px; background: white;" />

</div>

<details>
<summary><b>Click to show/hide raw Mermaid source code</b></summary>

```mermaid
flowchart TD
    subgraph INGRESS ["1. Query Reception & Context Gathering"]
        CL["Student Client"]
        SS[("Session Store")]
        P1["P3.1 Query
Reception"]
        P2["P3.2 Context
Injection"]
        AD[("Academic DB")]
    end
    
    subgraph RAG_LLM ["2. RAG Retrieval & LLM Pipeline"]
        P3["P3.3 RAG
Retrieval"]
        FI[("FAISS Index")]
        P4["P3.4 PII
Redaction"]
        LM["External LLM"]
        P5["P3.5 Response
Streaming"]
    end

    CL --"query"--> P1
    SS --"history"--> P1
    P1 --> P2
    AD --"data"--> P2
    P2 --> P3
    FI --"passages"--> P3
    P3 --> P4
    P4 --> LM
    LM --> P5
    P5 --"stream"--> CL
    P5 --"save"--> SS
```

</details>

**AI Pipeline Walkthrough:**
1. **P3.1 (Query Reception):** Intercepts the inbound query, verifies the session token, and pulls conversational history from the Redis Session Store.
2. **P3.2 (Academic Context Injection):** Queries the student's marks and risk signals from D1: Academic Database and appends them to the system prompt to ground the AI's response.
3. **P3.3 (RAG Retrieval):** Embeds the user query and searches the FAISS Vector Index for top-k course notes, syllabi, and faculty-uploaded materials.
4. **P3.4 (PII Redaction):** Applies regex-based filters to scrub student names, registration IDs, email addresses, and phone numbers from the prompt before external transmission.
5. **P3.5 (Response Streaming):** Consumes raw SSE tokens from the LLM, streams them to the Student Client in real-time, and persists the final transcript in the Session Store.

---

## 3.6 Figure 3.6: System Flow Diagram (SFD) — Request Life Cycle

<div align="center">

<img src="https://mermaid.ink/svg/eyJjb2RlIjogImZsb3djaGFydCBURFxuICAgIFNUW1wiQ2xpZW50IEJyb3dzZXJcIl1cbiAgICBTMVtcIjEuIFRMUyAmIFJhdGUgTGltaXRcIl1cbiAgICBTMltcIjIuIEpXVCBWZXJpZnlcIl1cbiAgICBTM1tcIjMuIFJvbGUgR3VhcmRcIl1cbiAgICBTNFtcIjQuIERCIFNjb3BpbmdcIl1cbiAgICBTNVtcIjUuIFJvdXRlciBEaXNwYXRjaFwiXVxuICAgIFM2W1wiNi4gU2VydmljZSBMYXllclwiXVxuICAgIFM3W1wiNy4gREIgVHJhbnNhY3Rpb25cIl1cbiAgICBTOFtcIjguIEF1ZGl0IExvZ1wiXVxuICAgIFM5W1wiOS4gUmVzcG9uc2VcIl1cbiAgICBFMVtcIjQyOSBSYXRlIEV4Y2VlZGVkXCJdXG4gICAgRTJbXCI0MDEgVW5hdXRob3Jpc2VkXCJdXG4gICAgRTNbXCI0MDMgRm9yYmlkZGVuXCJdXG4gICAgU1QtLT5TMVxuICAgIFMxLS1cIk9LXCItLT5TMlxuICAgIFMxLS5cImV4Y2VlZGVkXCIuLT5FMVxuICAgIFMyLS1cInZhbGlkXCItLT5TM1xuICAgIFMyLS5cImludmFsaWRcIi4tPkUyXG4gICAgUzMtLVwiYXV0aG9yaXNlZFwiLS0-UzRcbiAgICBTMy0uXCJmb3JiaWRkZW5cIi4tPkUzXG4gICAgUzQtLT5TNVxuICAgIFM1LS0-UzZcbiAgICBTNi0tPlM3XG4gICAgUzctLT5TOFxuICAgIFM4LS0-UzlcbiAgICBTOS0tXCIyMDAgT0tcIi0tPlNUIiwgIm1lcm1haWQiOiB7InRoZW1lIjogImJhc2UiLCAidGhlbWVWYXJpYWJsZXMiOiB7InByaW1hcnlDb2xvciI6ICIjZmZmZmZmIiwgInByaW1hcnlUZXh0Q29sb3IiOiAiIzAwMDAwMCIsICJwcmltYXJ5Qm9yZGVyQ29sb3IiOiAiIzAwMDAwMCIsICJsaW5lQ29sb3IiOiAiIzAwMDAwMCIsICJzZWNvbmRhcnlDb2xvciI6ICIjZmZmZmZmIiwgInRlcnRpYXJ5Q29sb3IiOiAiI2ZmZmZmZiIsICJmb250U2l6ZSI6ICIxMnB4In19fQ" alt="System Flow Diagram" style="max-width: 100%; max-height: 250mm; border: 1px solid #ddd; padding: 10px; background: white;" />

</div>

<details>
<summary><b>Click to show/hide raw Mermaid source code</b></summary>

```mermaid
flowchart TD
    ST["Client Browser"]
    S1["1. TLS & Rate Limit"]
    S2["2. JWT Verify"]
    S3["3. Role Guard"]
    S4["4. DB Scoping"]
    S5["5. Router Dispatch"]
    S6["6. Service Layer"]
    S7["7. DB Transaction"]
    S8["8. Audit Log"]
    S9["9. Response"]
    E1["429 Rate Exceeded"]
    E2["401 Unauthorised"]
    E3["403 Forbidden"]
    ST-->S1
    S1--"OK"-->S2
    S1-."exceeded".->E1
    S2--"valid"-->S3
    S2-."invalid".->E2
    S3--"authorised"-->S4
    S3-."forbidden".->E3
    S4-->S5
    S5-->S6
    S6-->S7
    S7-->S8
    S8-->S9
    S9--"200 OK"-->ST
```

</details>

**Request Lifecycle Walkthrough:**

| Step | Layer | Description |
|:-----|:------|:------------|
| **1** | Security | HTTPS request enters; SlowAPI checks IP rate (200 req/min). Exceeding returns `429`. |
| **2** | Security | JWT dependency extracts Bearer token, verifies signature and expiry. Failure returns `401`. |
| **3** | Security | Role claim is checked against endpoint requirement. Mismatch returns `403`. |
| **4** | Application | Scope helper appends `WHERE` clause filter to constrain DB queries to the authenticated principal. |
| **5** | Application | FastAPI routes request to the correct domain router (academic, campus, user, staff). |
| **6** | Application | Route handler delegates all business logic to the corresponding service module. |
| **7** | Persistence | SQLAlchemy session executes DB operations; committed on success, rolled back on exception. |
| **8** | Compliance | AuditLogMiddleware intercepts state-changing responses and appends an immutable JSON diff record. |
| **9** | Response | Pydantic model serialises the result and returns the appropriate HTTP status code to the client. |

---

<div align="center">

*Studvisor System Design — Chapter 3 Technical Diagrams © 2026*

</div>

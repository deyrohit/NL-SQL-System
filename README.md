# NL-SQL-System

```mermaid
flowchart TD

    %% =====================
    %% AUTHENTICATION
    %% =====================

    Login([Login])
        --> Role{Determine Role<br/>User or Admin?}

    %% =====================
    %% USER FLOW (WITH MEMORY)
    %% =====================

    Role -->|User| UserMemory[ConversationBufferWindowMemory<br/>k = 5]

    UserMemory --> UserModel[Model Generates SQL Query]

    UserModel --> UserSQL[Generated SQL Query]

    UserSQL --> UserValidate{User SQL Validation}

    %% Rejection Reasons - Modification Blocked
    UserValidate -->|INSERT / UPDATE / DELETE / DROP| Reject1["Reject: Data Modification Not Allowed<br/>Users are restricted to read-only access"]
    
    %% Only SELECT Allowed
    UserValidate -->|Not SELECT| Reject2["Reject: Only SELECT Queries Allowed<br/>Users can only retrieve data"]
    
    %% Block Schema Modification
    UserValidate -->|CREATE / ALTER / SCHEMA| Reject3["Reject: Schema Modification Not Allowed<br/>Users cannot modify database structure"]
    
    %% Block Schema Visibility / Metadata Access
    UserValidate -->|information_schema / pg_catalog / pg_tables / pg_class| Reject4["Reject: Schema Visibility Restricted<br/>Users cannot view database schema or metadata"]

    %% Valid Query
    UserValidate -->|Valid SELECT| UserSanitize[Add/Enforce LIMIT Clause]

    %% Explanation then Access Message
    Reject1 --> AccessMsg
    Reject2 --> AccessMsg
    Reject3 --> AccessMsg
    Reject4 --> AccessMsg

    AccessMsg["We don’t have access to this information.<br/>Please contact the admin."]
        --> EndUser([Return to User])


    %% =====================
    %% ADMIN FLOW (NO MEMORY)
    %% =====================

    Role -->|Admin| AdminModel[Model Generates SQL Query]

    AdminModel --> AdminSQL[Generated SQL Query]

    AdminSQL --> ConfirmStep{Are you sure you want to execute this operation?}

    ConfirmStep -->|Yes| AdminExecute[Execute CRUD on PostgreSQL]
    ConfirmStep -->|No| CancelOp[Operation Cancelled]

    CancelOp --> EndAdmin([Return to Admin])


    %% =====================
    %% EXECUTION LAYER
    %% =====================

    UserSanitize --> ExecuteUser[Execute SQL on PostgreSQL]

    ExecuteUser -->|Query Error| DBError[Database Error]
    DBError --> AccessMsg

    ExecuteUser -->|Success| UserResults[Fetch Results as JSON]

    AdminExecute -->|Query Error| DBErrorAdmin[Database Error]
    DBErrorAdmin --> EndAdmin

    AdminExecute -->|Success| AdminResults[Return Operation Status<br/>Rows Affected / Success Message]


    %% =====================
    %% USER RESPONSE FLOW
    %% =====================

    UserResults --> Count{Has Results?}

    Count -->|Has Results| GenerateAnswer[Generate Natural Language Answer]

    Count -->|No Results| NoData["Generate 'No Results' Message"]

    GenerateAnswer --> UserResponse["Format User Response:<br/>
    - Answer Text<br/>
    - SQL Query"]

    NoData --> UserResponse

    UserResponse --> EndUser


    %% =====================
    %% ADMIN RESPONSE FLOW
    %% =====================

    AdminResults --> AdminResponse["Format Admin Response:<br/>
    - Operation Type (CREATE/UPDATE/DELETE/DROP)<br/>
    - Rows Affected<br/>
    - Execution Status<br/>
    - Timestamp"]

    AdminResponse --> EndAdmin


    %% =====================
    %% STYLING
    %% =====================

    style Login fill:#4CAF50,color:#fff
    style EndUser fill:#4CAF50,color:#fff
    style EndAdmin fill:#4CAF50,color:#fff
    style AccessMsg fill:#f44336,color:#fff
    style ExecuteUser fill:#2196F3,color:#fff
    style AdminExecute fill:#673AB7,color:#fff
    style UserMemory fill:#FFC107,color:#000

'''

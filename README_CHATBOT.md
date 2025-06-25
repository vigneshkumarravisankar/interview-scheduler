# Advanced Multi-Contextual Chatbot System

## Overview

This project now includes a comprehensive multi-contextual chatbot system that provides intelligent, professional assistance for interview management. The chatbot supports natural language processing, context-aware conversations, specialized agent integration, and database querying capabilities.

## Features

### 🤖 **Multi-Contextual Conversations**
- **Context Recognition**: Automatically detects and maintains conversation context across multiple domains:
  - `general` - General conversation and help
  - `job_management` - Job posting creation and management
  - `candidate_management` - Candidate application processing
  - `interview_process` - Interview scheduling and shortlisting
  - `database_query` - Data search and filtering
  - `analytics` - Reports and performance metrics
  - `scheduling` - Calendar and time management
  - `technical_support` - System help and troubleshooting

### 🧠 **Intent Classification**
- **Smart Intent Recognition**: Understands user intentions:
  - `greeting` - Welcome messages and introductions
  - `question` - Information requests and inquiries
  - `command` - Direct action requests
  - `request` - Service or assistance requests
  - `complaint` - Issues and problems
  - `compliment` - Positive feedback
  - `goodbye` - Conversation endings
  - `help` - Support and guidance requests

### 🎯 **Professional Response Types**
- **Structured Responses**: Provides appropriate response formats:
  - `informational` - Knowledge sharing and explanations
  - `confirmational` - Action confirmations and status updates
  - `instructional` - Step-by-step guidance
  - `error` - Error messages with recovery suggestions
  - `success` - Completion confirmations
  - `warning` - Important notices and alerts

### 🔧 **Specialized Agent Integration**
- **Seamless Agent Routing**: Direct integration with specialized AI agents:
  - **Shortlisting Agent**: Selects top candidates based on AI fit scores
  - **Scheduling Agent**: Manages interview scheduling with calendar integration
  - **End-to-End Agent**: Complete hiring process automation
  - **Job Management Agent**: Creates and manages job postings

### 🗃️ **Database Querying**
- **Natural Language Database Access**: Query system data using natural language:
  - Job posting searches and filters
  - Candidate profile queries
  - Interview status tracking
  - Analytics and reporting
  - Multi-collection data correlation

### 🔍 **NLP Processing**
- **Advanced Text Analysis**:
  - Entity extraction (emails, dates, job IDs, names, numbers)
  - Keyword identification and categorization
  - Parameter extraction from natural language
  - Confidence scoring for responses
  - Contextual suggestion generation

## API Endpoints

### Core Chat Endpoints

#### `POST /chat/advanced/query`
Main chatbot query endpoint with comprehensive response handling.

**Request:**
```json
{
  "message": "Create a software engineer job with 3 years experience",
  "sessionId": "optional-session-id",
  "context": {}
}
```

**Response:**
```json
{
  "message": "I'll help you create a software engineer job posting...",
  "sessionId": "uuid-v4-session-id",
  "context": "job_management",
  "intent": "command",
  "confidence": 0.95,
  "response_type": "success",
  "executed_actions": [
    {
      "type": "job_creation",
      "agent": "job_management",
      "result": {...}
    }
  ],
  "suggestions": [
    "View the created job",
    "Add more details",
    "Process applications"
  ],
  "metadata": {
    "timestamp": "2025-01-01T12:00:00Z",
    "model_used": "gpt-4o",
    "processing_time": 1.25
  }
}
```

#### `POST /chat/advanced/conversation/start`
Start a new conversation session.

**Response:**
```json
{
  "conversation_id": "uuid-v4",
  "message": "Hello! I'm your AI assistant...",
  "context": "general",
  "suggestions": ["Create a job", "View candidates", "Help"]
}
```

#### `GET /chat/advanced/conversation/{id}/history`
Get conversation history for a session.

**Response:**
```json
{
  "conversation_id": "uuid-v4",
  "history": [
    {
      "timestamp": "2025-01-01T12:00:00Z",
      "user": "Hello",
      "assistant": "Hi there! How can I help?",
      "context": "general",
      "intent": "greeting",
      "confidence": 0.98
    }
  ],
  "total_messages": 10
}
```

### Utility Endpoints

#### `POST /chat/advanced/analyze`
Analyze a message for intent, context, and entities.

**Request:**
```json
{
  "message": "Schedule interviews for software engineer candidates"
}
```

**Response:**
```json
{
  "message": "Schedule interviews for software engineer candidates",
  "analysis": {
    "context": "interview_process",
    "intent": "command",
    "confidence": 0.92,
    "primary_topic": "interview scheduling",
    "requires_database": true,
    "requires_agent": true,
    "entities": {
      "job_roles": ["software engineer"],
      "dates": [],
      "emails": []
    },
    "keywords": ["schedule", "interviews", "candidates"]
  }
}
```

#### `GET /chat/advanced/capabilities`
Get comprehensive information about chatbot capabilities.

**Response:**
```json
{
  "capabilities": {
    "contexts": [...],
    "specialized_agents": [...],
    "features": [...],
    "response_types": [...]
  },
  "version": "1.0.0",
  "model": "gpt-4o"
}
```

## Usage Examples

### Job Management
```
User: "Create a software engineer job for someone with 3-5 years experience in San Francisco"
Assistant: "I'll create a software engineer job posting for you with the specified requirements..."
Context: job_management
Actions: [job_creation_agent_executed]
```

### Candidate Management
```
User: "Show me all candidates who applied for the developer position"
Assistant: "Here are the candidates for the developer position..."
Context: candidate_management
Actions: [database_query_executed]
```

### Interview Process
```
User: "Shortlist top 3 candidates for the software engineer role"
Assistant: "I'll analyze all candidates and select the top 3 based on AI fit scores..."
Context: interview_process
Actions: [shortlisting_agent_executed]
```

### Database Queries
```
User: "Find candidates with Python and React skills"
Assistant: "I found 12 candidates with Python and React experience..."
Context: database_query
Actions: [database_search_executed]
```

### Analytics
```
User: "Show me interview success rates for this month"
Assistant: "Here are the interview statistics for this month..."
Context: analytics
Actions: [analytics_report_generated]
```

## Demo Interface

### Access Points
- **Basic Chatbot**: http://localhost:8000/chatbot
- **Advanced Chatbot**: http://localhost:8000/advanced-chatbot
- **Agent Interface**: http://localhost:8000/agent
- **Firebase Query**: http://localhost:8000/firebase-query

### Advanced Demo Features
- **Real-time Chat**: Interactive chat interface with typing indicators
- **Context Visualization**: Shows current context and confidence levels
- **Action Tracking**: Displays executed actions and their results
- **Suggestion Chips**: Quick action buttons for common tasks
- **Export Functionality**: Download chat history as JSON
- **Responsive Design**: Works on desktop and mobile devices

### Quick Actions Available
- View Jobs
- View Candidates  
- Shortlist Process
- Schedule Interviews
- Create Job Postings
- Run Analytics

## Architecture

### Service Layer
- **AdvancedChatbotService**: Main service class handling all chatbot logic
- **Context Managers**: Specialized managers for different conversation contexts
- **Analysis Engine**: Message analysis for intent and entity extraction
- **Response Generation**: Contextual response creation with appropriate formatting

### Database Integration
- **Conversation History**: Stored in `advanced_chat_histories` collection
- **Feedback System**: User feedback stored in `chatbot_feedback` collection
- **Context Persistence**: Maintains conversation state across sessions

### Agent Integration
- **Direct Agent Access**: Seamless integration with existing specialized agents
- **Parameter Extraction**: Automatic parameter extraction from natural language
- **Result Processing**: Agent results processed and formatted for user consumption

## Configuration

### Environment Variables
```bash
OPENAI_API_KEY=your-openai-api-key
FIREBASE_CREDENTIALS=path-to-firebase-credentials.json
```

### Model Configuration
- **Primary Model**: GPT-4o for conversation and analysis
- **Temperature**: 0.3 for balanced creativity and consistency
- **Max Tokens**: 2000 for comprehensive responses

## Error Handling

### Fallback Mechanisms
- **Service Failures**: Falls back to basic chatbot service
- **API Errors**: Provides user-friendly error messages
- **Network Issues**: Graceful degradation with retry suggestions
- **Invalid Inputs**: Clear validation messages with examples

### Logging and Monitoring
- **Comprehensive Logging**: All interactions logged for debugging
- **Performance Tracking**: Response times and processing metrics
- **Error Tracking**: Detailed error logs with context information

## Extending the System

### Adding New Contexts
1. Add context to `ConversationContext` enum
2. Create corresponding context manager class
3. Update analysis prompts to recognize new context
4. Add context-specific response handling

### Adding New Agents
1. Create agent function in appropriate module
2. Add agent registration in service initialization
3. Update agent type determination logic
4. Add agent-specific parameter extraction

### Customizing Responses
1. Modify response templates in service methods
2. Update formatting functions for new response types
3. Add custom suggestion generation logic
4. Implement domain-specific response handlers

## Performance Considerations

### Optimization Strategies
- **Context Caching**: Frequently used contexts cached for faster access
- **Response Streaming**: Large responses streamed for better UX
- **Database Indexing**: Optimized queries for conversation history
- **Async Processing**: Non-blocking operations for better concurrency

### Scalability Features
- **Session Management**: Distributed session storage support
- **Load Balancing**: Stateless design for horizontal scaling
- **Caching Layer**: Redis integration for high-performance caching
- **Rate Limiting**: Built-in protection against abuse

## Security

### Data Protection
- **Input Sanitization**: All user inputs sanitized and validated
- **SQL Injection Prevention**: Parameterized queries only
- **XSS Protection**: HTML content properly escaped
- **Session Security**: Secure session management with proper timeouts

### Privacy Features
- **Data Retention**: Configurable conversation history retention
- **Anonymization**: PII detection and handling
- **Audit Logging**: Comprehensive audit trails for compliance
- **Access Controls**: Role-based access to sensitive features

---

## Getting Started

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**:
   ```bash
   export OPENAI_API_KEY=your-key-here
   ```

3. **Run the Application**:
   ```bash
   python run.py
   ```

4. **Access the Demo**:
   - Open http://localhost:8000/advanced-chatbot
   - Start chatting with the AI assistant!

The advanced multi-contextual chatbot is now ready to handle professional interview management conversations with the intelligence and capabilities of ChatGPT, specialized for your domain!

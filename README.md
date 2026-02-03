# ai-issue-agent
This project is an AI agent that triages software project issues from a chat platform

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AI Issue Agent                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │  Chat Adapters  │    │   VCS Adapters  │    │  LLM Adapters   │          │
│  │  (Abstract)     │    │   (Abstract)    │    │  (Abstract)     │          │
│  ├─────────────────┤    ├─────────────────┤    ├─────────────────┤          │
│  │ • Slack         │    │ • GitHub        │    │ • OpenAI        │          │
│  │ • Discord*      │    │ • GitLab*       │    │ • Anthropic     │          │
│  │ • MS Teams*     │    │ • Bitbucket*    │    │ • Ollama/Llama  │          │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘          │
│           │                      │                      │                   │
│           └──────────────────────┼──────────────────────┘                   │
│                                  │                                          │
│                    ┌─────────────▼─────────────┐                            │
│                    │      Core Engine          │                            │
│                    │  ┌─────────────────────┐  │                            │
│                    │  │ Message Processor   │  │                            │
│                    │  │ Traceback Parser    │  │                            │
│                    │  │ Issue Matcher       │  │                            │
│                    │  │ Code Analyzer       │  │                            │
│                    │  │ Issue Creator       │  │                            │
│                    │  └─────────────────────┘  │                            │
│                    └───────────────────────────┘                            │
│                                                                             │
│  * = Future implementation                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

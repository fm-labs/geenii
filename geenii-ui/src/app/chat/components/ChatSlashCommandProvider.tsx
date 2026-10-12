import React from 'react'
import { ChatContext } from '@/app/chat/components/ChatContext.tsx'
import { AVAILABLE_MODELS } from '@/constants.ts'
import { useNavigate } from '@/app-router.tsx'
import { ChatMessageCompat } from '@/app/chat/components/chat.types.ts'

const ChatSlashCommandProvider = () => {

  const chatContext = React.useContext(ChatContext)
  if (!chatContext) {
    throw new Error('ChatContext is not provided')
  }
  const { messages, addMessage, setMessages, modelName, setModelName, isThinking, tools } = chatContext
  const navigate = useNavigate()

  const addMessageCompat = (message: ChatMessageCompat) => {
    addMessage({
      role: message.role,
      content: [
        { type: message.type, text: message.content}
      ],
    })
  }

  const commandHandler = async (command: string) => {
    // Handle slash commands here
    console.log("Slash command received:", command);
    // You can add logic to process the command and update messages or tools accordingly

    const parts = command.split(' ');

    switch (parts[0]) {
      case "/help":
        const commandsList = [
          '/help - Show this help message',
          '/models - List available models',
          '/set-model \<model_name\> - Set the model to use for chat completions',
          '/tools - List available tools',
          '/call-tool \<tool_name\> \[...\<args\>\] - Call a specific tool with arguments',
          '/clear - Clear the chat messages',
          '/navigate  \<url\> - Navigate to a specific URL',
        ];
        const content = `You can use the following commands to interact with the chat system:\n- ${commandsList.join('\n - ')}`;
        addMessageCompat({ role: 'system', type: 'text', content: content });
        break;
      case "/navigate":
        if (parts.length < 2) {
          addMessageCompat({ role: 'system', type: 'text', content: 'Usage: /navigate <url>' });
          return;
        }
        const url = parts.slice(1).join(' ');
        addMessageCompat({ role: 'system', type: 'text', content: `Navigating to ${url}...` });
        setTimeout(() => navigate(url), 1000);
        break;
      case "/models":
        addMessageCompat({ role: 'system', type: 'text', content: `Available models:\n ${AVAILABLE_MODELS.join('\n - ')}` });
        break;
      case "/set-model":
        if (parts.length < 2) {
          addMessageCompat({ role: 'system', type: 'text', content: 'Usage: /set-model <model_name>' });
          return;
        }

        let modelName = parts[1];
        if (modelName === 'default') {
          modelName = AVAILABLE_MODELS[0]; // Reset to default model
        } else if (!AVAILABLE_MODELS.includes(modelName)) {
          addMessageCompat({ role: 'system', type: 'text', content: `Model ${modelName} is not available.` });
          return;
        }
        setModelName(modelName)
        addMessageCompat({ role: 'system', type: 'text', content: `Model set to ${modelName}.` });
        break;
      case "/clear":
        setMessages([]);
        break;
      case "/tools":
        // generate a list of tools as a string
        const toolList = tools.length > 0 ? tools.join(', ') : 'No tools';
        addMessageCompat({ role: 'system', type: 'text', content: `Available tools: ${toolList}` });
        break;
      default:
        addMessageCompat({ role: 'system', type: 'text', content: `Unknown command: ${command}` });
        console.warn(`Unknown command: ${command}`);
        break;
    }
  }

  return (
    <div>

    </div>
  )
}

export default ChatSlashCommandProvider
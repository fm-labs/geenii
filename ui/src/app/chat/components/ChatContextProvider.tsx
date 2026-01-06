import React, { PropsWithChildren, useState } from 'react'
import { ChatContext } from './ChatContext.tsx'
import { UploadedFile } from '../../../ui/file-list'
import { AVAILABLE_MODELS } from '../../../constants.ts'
import { useNavigate } from '../../../app-router.tsx'
import { ChatMessage } from '@/app/chat/components/chat.types.ts'

interface ChatContextProviderProps extends PropsWithChildren<any>{
    chatId?: string;
    modelName?: string;
    initialMessages?: any[];
    initialTools?: string[];
    initialFiles?: UploadedFile[];
    commandHandler?: (command: string) => void;
}

const ChatContextProvider = (props: ChatContextProviderProps) => {

    const [modelName, setModelName] = useState(props.modelName || AVAILABLE_MODELS[0]);
    //const messages = React.useRef<ChatMessage[]>([])
    const [messages, setMessages] = useState<any[]>(props.initialMessages || []);
    const [tools, setTools] = useState<string[]>(props.initialTools || []);
    const [files, setFiles] = useState<UploadedFile[]>(props.initialFiles || []);
    const [isThinking, setIsThinking] = React.useState<boolean>(false)

    const navigate = useNavigate();

    const addMessage = (message: ChatMessage) => {
        console.log('>> ADD MESSAGE', message)
        //messages.push(message)
        //setMessages([...messages, message] )// update messages in context
        setMessages(prevMessages => [
            ...prevMessages,
            message
        ]);
    }

    const contextValue = {
        chatId: props.chatId, // This can be set dynamically based on your application logic
        modelName,
        setModelName,
        messages,
        setMessages,
        addMessage,
        tools,
        setTools,
        files,
        setFiles,
        isThinking,
        setIsThinking,
        //commandHandler: props?.commandHandler,
    }

    React.useEffect(() => {
        console.log(">> ChatContextProvider initialMessages changed", props.initialMessages);
        setMessages(props.initialMessages || []);
    }, [props.initialMessages]);

    return (
        <ChatContext.Provider value={contextValue}>
            {props.children}
        </ChatContext.Provider>
    );
};

export default ChatContextProvider;

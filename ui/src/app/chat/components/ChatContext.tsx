import React from "react";
import { UploadedFile } from "../../../ui/file-list";
import { ChatMessage } from '@/app/chat/components/chat.types.ts'

type ChatContextType = {
    chatId?: string;
    modelName?: string;
    setModelName: (modelName: string) => void;
    messages: ChatMessage[];
    setMessages: (messages: ChatMessage[]) => void;
    addMessage: (message: ChatMessage) => void;
    tools: string[];
    setTools: (tools: string[]) => void;
    files: UploadedFile[];
    setFiles: (files: UploadedFile[]) => void;
    isThinking: boolean;
    setIsThinking: (thinking: boolean) => void;
    commandHandler?: (command: string) => Promise<void>;
}

export const ChatContext = React.createContext<ChatContextType>(null)


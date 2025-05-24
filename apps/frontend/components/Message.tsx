import React from 'react';
import { Message as MessageType } from '@/types/spreadsheet';
import clsx from 'clsx';
import { Bot, User } from 'lucide-react';

type SectionProps = {
  title: string;
  content: string;
};

const Section: React.FC<SectionProps> = ({ title, content }) => {
  // Process cell references in section content
  const parts = content.split(/(@[\w!:.]+)/g);
  
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 mb-3 shadow-sm">
      <div className="font-semibold text-gray-900 text-sm mb-2 flex items-center gap-2">
        <div className="w-1.5 h-1.5 bg-blue-600 rounded-full" />
        {title}
      </div>
      <div className="text-gray-700 text-sm leading-relaxed">
        {parts.map((part, i) => 
          part.match(/^@[\w!:.]+$/) 
            ? <span key={i} className="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-medium text-xs">{part}</span>
            : <span key={i}>{part}</span>
        )}
      </div>
    </div>
  );
};

type MessageProps = {
  message: MessageType;
};

/**
 * Message component that renders chat messages with support for section bubbles
 * when message content contains headings (## Title)
 */
const Message: React.FC<MessageProps> = ({ message }) => {
  // Don't process sections for user messages
  if (message.role === 'user') {
    const parts = message.content.split(/(@[\w!:.]+)/g);
    return (
      <div className="flex justify-end mb-4">
        <div className="flex items-start gap-2 max-w-[80%]">
          <div className="bg-blue-600 text-white rounded-2xl rounded-tr-md px-4 py-3 shadow-sm">
            <div className="text-sm leading-relaxed">
              {parts.map((part, i) => 
                part.match(/^@[\w!:.]+$/) 
                  ? <span key={i} className="bg-blue-500 text-white px-1.5 py-0.5 rounded font-medium text-xs">{part}</span>
                  : <span key={i}>{part}</span>
              )}
            </div>
          </div>
          <div className="w-7 h-7 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
            <User size={14} className="text-blue-600" />
          </div>
        </div>
      </div>
    );
  }

  // For system messages, render as a welcome card
  if (message.role === 'system') {
    return (
      <div className="mb-6">
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-4 text-center shadow-sm">
          <div className="flex items-center justify-center mb-3">
            <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center">
              <Bot size={18} className="text-white" />
            </div>
          </div>
          <h3 className="font-semibold text-gray-900 text-sm mb-2">Welcome to cf0 AI Assistant</h3>
          <p className="text-gray-600 text-sm leading-relaxed">
            I can help you analyze your data, create formulas, and modify your spreadsheet based on your instructions.
          </p>
          <div className="mt-4 text-xs text-gray-500">
            💡 Tip: Type @ to select cell ranges as context
          </div>
        </div>
      </div>
    );
  }

  // For assistant messages, check for sections (## headings)
  // Pattern: ## Heading\nContent until next heading or end
  const sectionPattern = /##\s+([^\n]+)(?:\n([\s\S]+?)(?=##|$))?/g;
  const matches = [...message.content.matchAll(sectionPattern)];
  
  // If no sections found or message is being streamed, render normally
  if (matches.length === 0 || message.status === 'thinking' || message.status === 'streaming') {
    const parts = message.content.split(/(@[\w!:.]+)/g);
    return (
      <div className="flex justify-start mb-4">
        <div className="flex items-start gap-2 max-w-[85%]">
          <div className="w-7 h-7 bg-gray-100 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
            <Bot size={14} className="text-gray-600" />
          </div>
          <div className={clsx(
            "bg-white border border-gray-200 rounded-2xl rounded-tl-md px-4 py-3 shadow-sm",
            message.status === 'streaming' ? "border-blue-200 bg-blue-50" : ""
          )}>
            {message.status === 'thinking' ? (
              <div className="flex items-center gap-2 text-gray-600">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-sm">Thinking...</span>
              </div>
            ) : (
              <div className="text-sm leading-relaxed text-gray-700">
                {parts.map((part, i) => 
                  part.match(/^@[\w!:.]+$/) 
                    ? <span key={i} className="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-medium text-xs">{part}</span>
                    : <span key={i}>{part}</span>
                )}
                {message.status === 'streaming' && (
                  <span className="inline-block w-2 h-5 bg-blue-600 ml-1 animate-pulse" />
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // If sections found and message is complete, render with sections
  const sections = [];
  let lastIndex = 0;
  
  // Extract regular text before the first section if any
  if (matches.length > 0 && matches[0].index! > 0) {
    const preambleText = message.content.substring(0, matches[0].index!).trim();
    if (preambleText) {
      const parts = preambleText.split(/(@[\w!:.]+)/g);
      sections.push(
        <div key="preamble" className="bg-white border border-gray-200 rounded-lg p-3 mb-3 shadow-sm">
          <div className="text-sm leading-relaxed text-gray-700">
            {parts.map((part, i) => 
              part.match(/^@[\w!:.]+$/) 
                ? <span key={`preamble-${i}`} className="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-medium text-xs">{part}</span>
                : <span key={`preamble-${i}`}>{part}</span>
            )}
          </div>
        </div>
      );
    }
  }
  
  // Extract sections
  for (const match of matches) {
    const [fullMatch, title, content = ''] = match;
    const index = match.index!;
    
    lastIndex = index + fullMatch.length;
    
    sections.push(
      <Section 
        key={`section-${index}`} 
        title={title.trim()} 
        content={content.trim()} 
      />
    );
  }
  
  // Extract any trailing text after the last section
  if (lastIndex < message.content.length) {
    const epilogueText = message.content.substring(lastIndex).trim();
    if (epilogueText) {
      const parts = epilogueText.split(/(@[\w!:.]+)/g);
      sections.push(
        <div key="epilogue" className="bg-white border border-gray-200 rounded-lg p-3 mb-3 shadow-sm">
          <div className="text-sm leading-relaxed text-gray-700">
            {parts.map((part, i) => 
              part.match(/^@[\w!:.]+$/) 
                ? <span key={`epilogue-${i}`} className="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-medium text-xs">{part}</span>
                : <span key={`epilogue-${i}`}>{part}</span>
            )}
          </div>
        </div>
      );
    }
  }
  
  return (
    <div className="flex justify-start mb-4">
      <div className="flex items-start gap-2 max-w-[90%]">
        <div className="w-7 h-7 bg-gray-100 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
          <Bot size={14} className="text-gray-600" />
        </div>
        <div className="space-y-0">
          {sections}
        </div>
      </div>
    </div>
  );
};

export default Message; 
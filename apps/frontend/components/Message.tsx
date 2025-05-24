import React from 'react';
import { Message as MessageType } from '@/types/spreadsheet';
import clsx from 'clsx';
import { Bot, User } from 'lucide-react';
import Image from 'next/image';

type SectionProps = {
  title: string;
  content: string;
};

const Section: React.FC<SectionProps> = ({ title, content }) => {
  // Process cell references in section content
  const parts = content.split(/(@[\w!:.]+)/g);
  
  return (
    <div className="bg-white rounded-xl border border-blue-200 p-4 mb-3 shadow-sm">
      <div className="font-semibold text-blue-900 text-sm mb-2 flex items-center gap-2">
        <div className="w-1.5 h-1.5 bg-blue-600 rounded-full" />
        {title}
      </div>
      <div className="text-gray-700 text-sm leading-relaxed">
        {parts.map((part, i) => 
          part.match(/^@[\w!:.]+$/) 
            ? <span key={i} className="bg-blue-100 text-blue-800 px-2 py-1 rounded-md font-medium text-xs">{part}</span>
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
        <div className="flex items-start gap-3 max-w-[80%]">
          <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-2xl rounded-tr-md px-4 py-3 shadow-md">
            <div className="text-sm leading-relaxed font-['Inter',_system-ui,_sans-serif]">
              {parts.map((part, i) => 
                part.match(/^@[\w!:.]+$/) 
                  ? <span key={i} className="bg-blue-500 text-white px-2 py-1 rounded-md font-medium text-xs">{part}</span>
                  : <span key={i}>{part}</span>
              )}
            </div>
          </div>
          <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 mt-1 shadow-sm">
            <User size={16} className="text-blue-600" />
          </div>
        </div>
      </div>
    );
  }

  // For system messages, render as a welcome card
  if (message.role === 'system') {
    return (
      <div className="mb-6">
        <div className="bg-gradient-to-r from-blue-50 to-blue-25 border border-blue-200 rounded-xl p-6 text-center shadow-md">
          <div className="flex items-center justify-center mb-4">
            <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl flex items-center justify-center shadow-md">
              <Image src="/logo.png" alt="cf0" width={28} height={28} className="rounded-sm" />
            </div>
          </div>
          <h3 className="font-bold text-blue-900 text-base mb-3">Welcome to cf0 AI Assistant</h3>
          <p className="text-blue-700 text-sm leading-relaxed font-['Inter',_system-ui,_sans-serif]">
            I can help you analyze your data, create formulas, and modify your spreadsheet based on your instructions.
          </p>
          <div className="mt-4 text-xs text-blue-600 bg-blue-100 px-3 py-2 rounded-lg inline-block">
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
        <div className="flex items-start gap-3 max-w-[85%]">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl flex items-center justify-center flex-shrink-0 mt-1 shadow-md">
            <Image src="/logo.png" alt="cf0" width={18} height={18} className="rounded-sm" />
          </div>
          <div className={clsx(
            "bg-white border rounded-2xl rounded-tl-md px-4 py-3 shadow-md",
            message.status === 'streaming' ? "border-blue-300 bg-blue-50" : "border-blue-200"
          )}>
            {message.status === 'thinking' ? (
              <div className="flex items-center gap-2 text-blue-600">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-sm font-medium">Thinking...</span>
              </div>
            ) : (
              <div className="text-sm leading-relaxed text-gray-700 font-['Inter',_system-ui,_sans-serif]">
                {parts.map((part, i) => 
                  part.match(/^@[\w!:.]+$/) 
                    ? <span key={i} className="bg-blue-100 text-blue-800 px-2 py-1 rounded-md font-medium text-xs">{part}</span>
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
        <div key="preamble" className="bg-white border border-blue-200 rounded-xl p-4 mb-3 shadow-md">
          <div className="text-sm leading-relaxed text-gray-700 font-['Inter',_system-ui,_sans-serif]">
            {parts.map((part, i) => 
              part.match(/^@[\w!:.]+$/) 
                ? <span key={`preamble-${i}`} className="bg-blue-100 text-blue-800 px-2 py-1 rounded-md font-medium text-xs">{part}</span>
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
        <div key="epilogue" className="bg-white border border-blue-200 rounded-xl p-4 mb-3 shadow-md">
          <div className="text-sm leading-relaxed text-gray-700 font-['Inter',_system-ui,_sans-serif]">
            {parts.map((part, i) => 
              part.match(/^@[\w!:.]+$/) 
                ? <span key={`epilogue-${i}`} className="bg-blue-100 text-blue-800 px-2 py-1 rounded-md font-medium text-xs">{part}</span>
                : <span key={`epilogue-${i}`}>{part}</span>
            )}
          </div>
        </div>
      );
    }
  }
  
  return (
    <div className="flex justify-start mb-4">
      <div className="flex items-start gap-3 max-w-[90%]">
        <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl flex items-center justify-center flex-shrink-0 mt-1 shadow-md">
          <Image src="/logo.png" alt="cf0" width={18} height={18} className="rounded-sm" />
        </div>
        <div className="space-y-0">
          {sections}
        </div>
      </div>
    </div>
  );
};

export default Message; 
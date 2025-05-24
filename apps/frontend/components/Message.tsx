import React from 'react';
import { Message as MessageType } from '@/types/spreadsheet';
import clsx from 'clsx';
import { User } from 'lucide-react';
import Image from 'next/image';

type SectionProps = {
  title: string;
  content: string;
};

const Section: React.FC<SectionProps> = ({ title, content }) => {
  // Process cell references in section content
  const parts = content.split(/(@[\w!:.]+)/g);
  
  return (
    <div className="bg-gray-900 rounded border border-gray-700 p-3 mb-2">
      <div className="font-mono text-gray-300 text-xs mb-2 flex items-center gap-2">
        <div className="w-1 h-1 bg-gray-500 rounded-full" />
        {title}
      </div>
      <div className="text-gray-400 text-xs leading-relaxed font-mono">
        {parts.map((part, i) => 
          part.match(/^@[\w!:.]+$/) 
            ? <span key={i} className="bg-gray-800 text-gray-300 px-1 py-0.5 rounded font-mono text-xs">{part}</span>
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
      <div className="flex justify-end mb-2">
        <div className="flex items-start gap-2 max-w-[80%]">
          <div className="bg-gray-800 text-gray-300 rounded px-2 py-1 border border-gray-700">
            <div className="text-xs leading-relaxed font-mono">
              {parts.map((part, i) => 
                part.match(/^@[\w!:.]+$/) 
                  ? <span key={i} className="bg-gray-700 text-gray-300 px-1 py-0.5 rounded font-mono text-xs">{part}</span>
                  : <span key={i}>{part}</span>
              )}
            </div>
          </div>
          <div className="w-4 h-4 bg-gray-800 rounded flex items-center justify-center flex-shrink-0 mt-0.5 border border-gray-700">
            <User size={10} className="text-gray-400" />
          </div>
        </div>
      </div>
    );
  }

  // For system messages, render as a welcome card
  if (message.role === 'system') {
    return (
      <div className="mb-3">
        <div className="bg-gray-900 border border-gray-700 rounded p-3 text-center">
          <div className="flex items-center justify-center mb-2">
            <div className="w-6 h-6 rounded flex items-center justify-center">
              <Image src="/logo.png" alt="cf0" width={16} height={16} className="rounded-sm" />
            </div>
          </div>
          <h3 className="font-mono text-gray-300 text-xs mb-1">cf0 AI Assistant</h3>
          <p className="text-gray-400 text-xs leading-relaxed font-mono">
            I can help you analyze your data, create formulas, and modify your spreadsheet.
          </p>
          <div className="mt-2 text-xs text-gray-500 bg-gray-800 px-2 py-1 rounded inline-block border border-gray-700 font-mono">
            💡 Type @ to select cell ranges
          </div>
        </div>
      </div>
    );
  }

  // For assistant messages, check for sections (## headings)
  // Pattern: ## Heading\nContent until next heading or end
  const sectionPattern = /##\s+([^\n]+)(?:\n([\s\S]+?)(?=##|$))?/g;
  const matches = [...message.content.matchAll(sectionPattern)];
  
  // If no sections found or message is being streamed, render as blue text without bubble
  if (matches.length === 0 || message.status === 'thinking' || message.status === 'streaming') {
    const parts = message.content.split(/(@[\w!:.]+)/g);
    return (
      <div className="flex justify-start mb-2">
        <div className="flex items-start gap-2 max-w-[85%]">
          <div className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0 mt-0.5">
            <Image src="/logo.png" alt="cf0" width={12} height={12} className="rounded-sm" />
          </div>
          <div className="text-blue-400 text-xs leading-relaxed font-mono">
            {message.status === 'thinking' ? (
              <div className="flex items-center gap-2">
                <div className="flex space-x-1">
                  <div className="w-1 h-1 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-1 h-1 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-1 h-1 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-xs font-mono">Thinking...</span>
              </div>
            ) : (
              <>
                {parts.map((part, i) => 
                  part.match(/^@[\w!:.]+$/) 
                    ? <span key={i} className="bg-gray-800 text-gray-300 px-1 py-0.5 rounded font-mono text-xs">{part}</span>
                    : <span key={i}>{part}</span>
                )}
                {message.status === 'streaming' && (
                  <span className="inline-block w-1 h-3 bg-blue-400 ml-0.5 animate-pulse" />
                )}
              </>
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
        <div key="preamble" className="bg-gray-900 border border-gray-700 rounded p-3 mb-2">
          <div className="text-xs leading-relaxed text-gray-300 font-mono">
            {parts.map((part, i) => 
              part.match(/^@[\w!:.]+$/) 
                ? <span key={`preamble-${i}`} className="bg-gray-800 text-gray-300 px-1 py-0.5 rounded font-mono text-xs">{part}</span>
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
        <div key="epilogue" className="bg-gray-900 border border-gray-700 rounded p-3 mb-2">
          <div className="text-xs leading-relaxed text-gray-300 font-mono">
            {parts.map((part, i) => 
              part.match(/^@[\w!:.]+$/) 
                ? <span key={`epilogue-${i}`} className="bg-gray-800 text-gray-300 px-1 py-0.5 rounded font-mono text-xs">{part}</span>
                : <span key={`epilogue-${i}`}>{part}</span>
            )}
          </div>
        </div>
      );
    }
  }
  
  return (
    <div className="flex justify-start mb-3">
      <div className="flex items-start gap-2 max-w-[90%]">
        <div className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0 mt-0.5">
          <Image src="/logo.png" alt="cf0" width={14} height={14} className="rounded-sm" />
        </div>
        <div className="space-y-0">
          {sections}
        </div>
      </div>
    </div>
  );
};

export default Message; 
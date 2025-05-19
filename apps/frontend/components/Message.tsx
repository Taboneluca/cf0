import React from 'react';
import { Message as MessageType } from '@/types/spreadsheet';
import clsx from 'clsx';

type SectionProps = {
  title: string;
  content: string;
};

const Section: React.FC<SectionProps> = ({ title, content }) => {
  // Process cell references in section content
  const parts = content.split(/(@[\w!:.]+)/g);
  
  return (
    <div className="message-section">
      <div className="message-section-title">{title}</div>
      <div className="message-section-content">
        {parts.map((part, i) => 
          part.match(/^@[\w!:.]+$/) 
            ? <span key={i} className="text-blue-600 font-semibold">{part}</span>
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
  // Base bubble style
  const baseBubble = "rounded-lg px-3 py-2 max-w-[90%] break-words";
  
  // Don't process sections for user messages
  if (message.role === 'user') {
    const parts = message.content.split(/(@[\w!:.]+)/g);
    return (
      <div className={clsx(baseBubble, "self-end bg-blue-500 text-white ml-auto")}>
        {parts.map((part, i) => 
          part.match(/^@[\w!:.]+$/) 
            ? <span key={i} className="font-semibold underline">{part}</span>
            : <span key={i}>{part}</span>
        )}
      </div>
    );
  }

  // For system messages, render simple italic text with smaller font
  if (message.role === 'system') {
    return (
      <div className="text-sm text-gray-500 whitespace-pre-wrap">
        {message.content}
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
      <div className={clsx(
        baseBubble, 
        "self-start bg-gray-100", 
        message.status === 'streaming' ? "message-streaming" : ""
      )}>
        {message.status === 'thinking' ? (
          <div className="message-thinking">Thinking...</div>
        ) : (
          <div className="whitespace-pre-wrap message-streaming">
            {parts.map((part, i) => 
              part.match(/^@[\w!:.]+$/) 
                ? <span key={i} className="text-blue-600 font-semibold">{part}</span>
                : <span key={i}>{part}</span>
            )}
            {message.status === 'streaming' && (
              <span className="animate-pulse inline-block ml-1 h-4 w-1 bg-gray-400 rounded"></span>
            )}
          </div>
        )}
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
        <div key="preamble" className="message-preamble">
          {parts.map((part, i) => 
            part.match(/^@[\w!:.]+$/) 
              ? <span key={`preamble-${i}`} className="text-blue-600 font-semibold">{part}</span>
              : <span key={`preamble-${i}`}>{part}</span>
          )}
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
        <div key="epilogue" className="message-epilogue">
          {parts.map((part, i) => 
            part.match(/^@[\w!:.]+$/) 
              ? <span key={`epilogue-${i}`} className="text-blue-600 font-semibold">{part}</span>
              : <span key={`epilogue-${i}`}>{part}</span>
          )}
        </div>
      );
    }
  }
  
  return (
    <div className="message message-assistant message-with-sections">
      {sections}
    </div>
  );
};

export default Message; 
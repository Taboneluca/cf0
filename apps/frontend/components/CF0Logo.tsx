import React from 'react';

interface CF0LogoProps {
  size?: number;
  className?: string;
}

export default function CF0Logo({ size = 48, className = '' }: CF0LogoProps) {
  return (
    <svg 
      width={size} 
      height={size} 
      viewBox="0 0 500 500" 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <rect x="40" y="40" width="320" height="320" rx="40" fill="currentColor" fillOpacity="0.1" />
      <rect x="90" y="90" width="320" height="320" rx="40" fill="currentColor" fillOpacity="0.2" />
      <rect x="140" y="140" width="320" height="320" rx="40" fill="currentColor" fillOpacity="0.3" />
      <g>
        {/* First row */}
        <circle cx="90" cy="90" r="25" fill="currentColor" fillOpacity="0.7" />
        <circle cx="190" cy="90" r="25" fill="currentColor" fillOpacity="0.7" />
        <circle cx="290" cy="90" r="25" fill="currentColor" fillOpacity="0.7" />
        <circle cx="390" cy="90" r="25" fill="currentColor" fillOpacity="0.7" />
        
        {/* Second row */}
        <circle cx="90" cy="190" r="25" fill="currentColor" fillOpacity="0.7" />
        <circle cx="190" cy="190" r="25" fill="currentColor" fillOpacity="0.7" />
        <circle cx="290" cy="190" r="25" fill="currentColor" fillOpacity="0.7" />
        <circle cx="390" cy="190" r="25" fill="currentColor" fillOpacity="0.7" />
        
        {/* Third row */}
        <circle cx="90" cy="290" r="25" fill="currentColor" fillOpacity="0.7" />
        <circle cx="190" cy="290" r="25" fill="currentColor" fillOpacity="0.7" />
        <circle cx="290" cy="290" r="25" fill="currentColor" fillOpacity="0.7" />
        <circle cx="390" cy="290" r="25" fill="currentColor" fillOpacity="0.7" />
        
        {/* Fourth row */}
        <circle cx="90" cy="390" r="25" fill="currentColor" fillOpacity="0.7" />
        <circle cx="190" cy="390" r="25" fill="currentColor" fillOpacity="0.7" />
        <circle cx="290" cy="390" r="25" fill="currentColor" fillOpacity="0.7" />
        <circle cx="390" cy="390" r="25" fill="currentColor" fillOpacity="0.7" />
      </g>
    </svg>
  );
} 
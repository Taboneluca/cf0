/**
 * Debugging utility to log and validate request payloads before they are sent to the backend.
 * This utility checks for common issues like null values, wrong data types, and missing required fields.
 * It provides detailed logging of the exact JSON being sent to help with debugging 422 validation errors.
 */

export interface LangServeRequest {
  mode: string;
  message: string;
  wid?: string;
  sid?: string;
  contexts?: string[];
  model?: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  sanitized: LangServeRequest | null;
}

export class LangServeDebugger {
  private static instance: LangServeDebugger;
  private debugEnabled: boolean;
  private logLevel: 'error' | 'warn' | 'info' | 'debug';

  constructor() {
    this.debugEnabled = process.env.NODE_ENV === 'development' || 
                       process.env.NEXT_PUBLIC_DEBUG_LANGSERVE === '1';
    this.logLevel = (process.env.NEXT_PUBLIC_LOG_LEVEL as any) || 'info';
  }

  static getInstance(): LangServeDebugger {
    if (!LangServeDebugger.instance) {
      LangServeDebugger.instance = new LangServeDebugger();
    }
    return LangServeDebugger.instance;
  }

  private log(level: string, message: string, data?: any) {
    if (!this.debugEnabled) return;

    const levels = ['error', 'warn', 'info', 'debug'];
    const currentLevelIndex = levels.indexOf(this.logLevel);
    const messageLevelIndex = levels.indexOf(level);

    if (messageLevelIndex <= currentLevelIndex) {
      const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
      const emoji = {
        error: '❌',
        warn: '⚠️',
        info: 'ℹ️',
        debug: '🔍'
      }[level] || '📝';

      console.log(`[${timestamp}] ${emoji} [LangServe] ${message}`, data || '');
    }
  }

  /**
   * Validate a LangServe request payload and return detailed validation results
   */
  validateRequest(payload: any): ValidationResult {
    const result: ValidationResult = {
      valid: true,
      errors: [],
      warnings: [],
      sanitized: null
    };

    this.log('debug', 'Validating LangServe request payload', payload);

    // Check for null or undefined payload
    if (!payload || typeof payload !== 'object') {
      result.valid = false;
      result.errors.push('Payload is null, undefined, or not an object');
      return result;
    }

    const sanitized: Partial<LangServeRequest> = {};

    // Validate required fields
    if (!payload.mode || typeof payload.mode !== 'string') {
      result.errors.push('Field "mode" is required and must be a string');
      result.valid = false;
    } else {
      sanitized.mode = payload.mode;
    }

    if (payload.message === undefined || payload.message === null) {
      result.errors.push('Field "message" is required');
      result.valid = false;
    } else if (typeof payload.message !== 'string') {
      result.errors.push('Field "message" must be a string');
      result.valid = false;
    } else {
      sanitized.message = payload.message;
    }

    // Validate optional fields with defaults
    if (payload.wid !== undefined) {
      if (payload.wid === null) {
        result.warnings.push('Field "wid" is null, will use default');
        sanitized.wid = 'default';
      } else if (typeof payload.wid !== 'string') {
        result.errors.push('Field "wid" must be a string if provided');
        result.valid = false;
      } else {
        sanitized.wid = payload.wid;
      }
    } else {
      sanitized.wid = 'default';
    }

    if (payload.sid !== undefined) {
      if (payload.sid === null) {
        result.warnings.push('Field "sid" is null, will use default');
        sanitized.sid = 'Sheet1';
      } else if (typeof payload.sid !== 'string') {
        result.errors.push('Field "sid" must be a string if provided');
        result.valid = false;
      } else {
        sanitized.sid = payload.sid;
      }
    } else {
      sanitized.sid = 'Sheet1';
    }

    // Validate contexts array
    if (payload.contexts !== undefined) {
      if (payload.contexts === null) {
        result.warnings.push('Field "contexts" is null, will use empty array');
        sanitized.contexts = [];
      } else if (!Array.isArray(payload.contexts)) {
        result.errors.push('Field "contexts" must be an array if provided');
        result.valid = false;
      } else {
        // Validate array contents
        const validContexts: string[] = [];
        payload.contexts.forEach((context: any, index: number) => {
          if (typeof context !== 'string') {
            result.warnings.push(`contexts[${index}] is not a string, filtering out`);
          } else {
            validContexts.push(context);
          }
        });
        sanitized.contexts = validContexts;
      }
    } else {
      sanitized.contexts = [];
    }

    // Validate optional model field
    if (payload.model !== undefined) {
      if (payload.model === null) {
        result.warnings.push('Field "model" is null, will be omitted');
        // Don't set sanitized.model
      } else if (typeof payload.model !== 'string') {
        result.errors.push('Field "model" must be a string if provided');
        result.valid = false;
      } else if (payload.model.trim() === '') {
        result.warnings.push('Field "model" is empty string, will be omitted');
        // Don't set sanitized.model
      } else {
        sanitized.model = payload.model.trim();
      }
    }

    // Check for unexpected fields
    const expectedFields = ['mode', 'message', 'wid', 'sid', 'contexts', 'model'];
    Object.keys(payload).forEach(key => {
      if (!expectedFields.includes(key)) {
        result.warnings.push(`Unexpected field "${key}" will be ignored`);
      }
    });

    if (result.valid && sanitized.mode && sanitized.message) {
      result.sanitized = sanitized as LangServeRequest;
    }

    this.log('debug', 'Validation complete', result);
    return result;
  }

  /**
   * Sanitize and log a request payload before sending
   */
  prepareRequest(payload: any): LangServeRequest | null {
    this.log('info', 'Preparing LangServe request', payload);

    const validation = this.validateRequest(payload);

    // Log validation results
    if (validation.errors.length > 0) {
      this.log('error', 'Request validation failed', {
        errors: validation.errors,
        originalPayload: payload
      });
      return null;
    }

    if (validation.warnings.length > 0) {
      this.log('warn', 'Request validation warnings', {
        warnings: validation.warnings,
        originalPayload: payload,
        sanitizedPayload: validation.sanitized
      });
    }

    if (validation.sanitized) {
      this.log('info', 'Request sanitized successfully', validation.sanitized);
      return validation.sanitized;
    }

    return null;
  }

  /**
   * Log a request being sent to the backend
   */
  logRequest(url: string, payload: any, method: string = 'POST') {
    this.log('info', `Sending ${method} request to ${url}`, {
      payload,
      timestamp: new Date().toISOString(),
      payloadSize: JSON.stringify(payload).length
    });
  }

  /**
   * Log a response received from the backend
   */
  logResponse(url: string, status: number, data?: any) {
    const level = status >= 400 ? 'error' : status >= 300 ? 'warn' : 'info';
    this.log(level, `Received response from ${url}`, {
      status,
      statusText: this.getStatusText(status),
      data: status >= 400 ? data : undefined,
      timestamp: new Date().toISOString()
    });
  }

  /**
   * Log streaming events
   */
  logStreamEvent(eventType: string, data?: any) {
    this.log('debug', `Stream event: ${eventType}`, data);
  }

  /**
   * Generate a test report for a request payload
   */
  generateTestReport(payload: any): string {
    const validation = this.validateRequest(payload);
    
    let report = `LangServe Request Test Report\n`;
    report += `=====================================\n`;
    report += `Timestamp: ${new Date().toISOString()}\n`;
    report += `Valid: ${validation.valid ? '✅' : '❌'}\n\n`;
    
    report += `Original Payload:\n`;
    report += `${JSON.stringify(payload, null, 2)}\n\n`;
    
    if (validation.sanitized) {
      report += `Sanitized Payload:\n`;
      report += `${JSON.stringify(validation.sanitized, null, 2)}\n\n`;
    }
    
    if (validation.errors.length > 0) {
      report += `Errors:\n`;
      validation.errors.forEach((error, index) => {
        report += `  ${index + 1}. ${error}\n`;
      });
      report += `\n`;
    }
    
    if (validation.warnings.length > 0) {
      report += `Warnings:\n`;
      validation.warnings.forEach((warning, index) => {
        report += `  ${index + 1}. ${warning}\n`;
      });
      report += `\n`;
    }
    
    return report;
  }

  private getStatusText(status: number): string {
    const statusTexts: Record<number, string> = {
      200: 'OK',
      201: 'Created',
      400: 'Bad Request',
      401: 'Unauthorized',
      403: 'Forbidden',
      404: 'Not Found',
      422: 'Unprocessable Entity',
      500: 'Internal Server Error'
    };
    return statusTexts[status] || 'Unknown';
  }
}

// Export singleton instance and utility functions
export const langServeDebugger = LangServeDebugger.getInstance();

export function validateLangServeRequest(payload: any): ValidationResult {
  return langServeDebugger.validateRequest(payload);
}

export function prepareLangServeRequest(payload: any): LangServeRequest | null {
  return langServeDebugger.prepareRequest(payload);
}

export function logLangServeRequest(url: string, payload: any, method?: string) {
  langServeDebugger.logRequest(url, payload, method);
}

export function logLangServeResponse(url: string, status: number, data?: any) {
  langServeDebugger.logResponse(url, status, data);
}

export function logLangServeStreamEvent(eventType: string, data?: any) {
  langServeDebugger.logStreamEvent(eventType, data);
}

export function generateLangServeTestReport(payload: any): string {
  return langServeDebugger.generateTestReport(payload);
} 
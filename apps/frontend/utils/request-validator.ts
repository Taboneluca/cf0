/**
 * Request Validator for LangServe Compatibility
 * 
 * This utility validates that requests are properly structured for LangServe compatibility.
 * It includes validation for both direct request formats and the wrapped input field format
 * that LangServe expects.
 */

export interface LangServeRequest {
  mode: string;
  message: string;
  wid: string;
  sid: string;
  contexts: string[];
  model?: string;
}

export interface LangServeInputWrapper {
  input: LangServeRequest;
}

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
  metadata: {
    format: 'direct' | 'wrapped' | 'unknown';
    payloadSize: number;
    hasRequiredFields: boolean;
    missingFields: string[];
  };
}

/**
 * Validates a direct LangServe request format
 */
export function validateDirectRequest(payload: any): ValidationResult {
  const result: ValidationResult = {
    isValid: true,
    errors: [],
    warnings: [],
    metadata: {
      format: 'direct',
      payloadSize: JSON.stringify(payload).length,
      hasRequiredFields: true,
      missingFields: []
    }
  };

  // Check required fields
  const requiredFields = ['mode', 'message', 'wid', 'sid'];
  const missingFields = requiredFields.filter(field => !(field in payload) || payload[field] === null || payload[field] === undefined);
  
  if (missingFields.length > 0) {
    result.isValid = false;
    result.metadata.hasRequiredFields = false;
    result.metadata.missingFields = missingFields;
    result.errors.push(`Missing required fields: ${missingFields.join(', ')}`);
  }

  // Validate field types
  if (payload.mode && typeof payload.mode !== 'string') {
    result.errors.push('Field "mode" must be a string');
    result.isValid = false;
  }

  if (payload.message && typeof payload.message !== 'string') {
    result.errors.push('Field "message" must be a string');
    result.isValid = false;
  }

  if (payload.wid && typeof payload.wid !== 'string') {
    result.errors.push('Field "wid" must be a string');
    result.isValid = false;
  }

  if (payload.sid && typeof payload.sid !== 'string') {
    result.errors.push('Field "sid" must be a string');
    result.isValid = false;
  }

  // Validate contexts array
  if ('contexts' in payload) {
    if (!Array.isArray(payload.contexts)) {
      result.errors.push('Field "contexts" must be an array');
      result.isValid = false;
    } else {
      const invalidContexts = payload.contexts.filter((ctx: any) => typeof ctx !== 'string');
      if (invalidContexts.length > 0) {
        result.warnings.push(`Non-string contexts detected: ${invalidContexts.length} items`);
      }
    }
  } else {
    result.warnings.push('Field "contexts" not provided - will default to empty array');
  }

  // Validate optional model field
  if ('model' in payload && payload.model !== null && typeof payload.model !== 'string') {
    result.errors.push('Field "model" must be a string or null');
    result.isValid = false;
  }

  // Check for null values that could cause issues
  Object.keys(payload).forEach(key => {
    if (payload[key] === null && key !== 'model') {
      result.warnings.push(`Field "${key}" is null - may cause validation issues`);
    }
  });

  return result;
}

/**
 * Validates a wrapped LangServe request format (with input field)
 */
export function validateWrappedRequest(payload: any): ValidationResult {
  const result: ValidationResult = {
    isValid: true,
    errors: [],
    warnings: [],
    metadata: {
      format: 'wrapped',
      payloadSize: JSON.stringify(payload).length,
      hasRequiredFields: true,
      missingFields: []
    }
  };

  // Check if input field exists
  if (!('input' in payload)) {
    result.isValid = false;
    result.errors.push('Missing required "input" field for LangServe wrapper');
    result.metadata.missingFields.push('input');
    result.metadata.hasRequiredFields = false;
    return result;
  }

  if (typeof payload.input !== 'object' || payload.input === null) {
    result.isValid = false;
    result.errors.push('Field "input" must be an object');
    return result;
  }

  // Validate the nested request
  const nestedValidation = validateDirectRequest(payload.input);
  
  // Merge validation results
  result.isValid = nestedValidation.isValid;
  result.errors = [...result.errors, ...nestedValidation.errors.map(err => `input.${err}`)];
  result.warnings = [...result.warnings, ...nestedValidation.warnings.map(warn => `input.${warn}`)];
  result.metadata.missingFields = nestedValidation.metadata.missingFields.map(field => `input.${field}`);
  result.metadata.hasRequiredFields = nestedValidation.metadata.hasRequiredFields;

  return result;
}

/**
 * Auto-detects the request format and validates accordingly
 */
export function validateLangServeRequest(payload: any): ValidationResult {
  if (!payload || typeof payload !== 'object') {
    return {
      isValid: false,
      errors: ['Payload must be an object'],
      warnings: [],
      metadata: {
        format: 'unknown',
        payloadSize: 0,
        hasRequiredFields: false,
        missingFields: []
      }
    };
  }

  // Determine format
  const hasInputField = 'input' in payload;
  const hasDirectFields = ['mode', 'message', 'wid', 'sid'].some(field => field in payload);

  if (hasInputField && !hasDirectFields) {
    // Wrapped format
    return validateWrappedRequest(payload);
  } else if (!hasInputField && hasDirectFields) {
    // Direct format
    return validateDirectRequest(payload);
  } else {
    // Ambiguous or invalid format
    return {
      isValid: false,
      errors: ['Ambiguous request format - cannot determine if direct or wrapped'],
      warnings: hasInputField ? ['Has input field but also has direct fields'] : [],
      metadata: {
        format: 'unknown',
        payloadSize: JSON.stringify(payload).length,
        hasRequiredFields: false,
        missingFields: []
      }
    };
  }
}

/**
 * Converts a direct request to wrapped format for LangServe compatibility
 */
export function wrapForLangServe(directRequest: LangServeRequest): LangServeInputWrapper {
  return {
    input: directRequest
  };
}

/**
 * Extracts a direct request from wrapped format
 */
export function unwrapFromLangServe(wrappedRequest: LangServeInputWrapper): LangServeRequest {
  return wrappedRequest.input;
}

/**
 * Sanitizes a request payload to ensure compatibility
 */
export function sanitizeRequestPayload(payload: any): LangServeRequest {
  return {
    mode: String(payload.mode || 'ask'),
    message: String(payload.message || ''),
    wid: String(payload.wid || 'default'),
    sid: String(payload.sid || 'Sheet1'),
    contexts: Array.isArray(payload.contexts) 
      ? payload.contexts.filter((ctx: any) => typeof ctx === 'string' && ctx.trim())
      : [],
    ...(payload.model && typeof payload.model === 'string' && payload.model.trim() && { model: payload.model.trim() })
  };
}

/**
 * Logs validation results in a structured format
 */
export function logValidationResult(result: ValidationResult, label: string = 'Request Validation'): void {
  if (process.env.NODE_ENV === 'development') {
    console.group(`🔍 ${label}`);
    
    if (result.isValid) {
      console.log('✅ Validation: PASSED');
    } else {
      console.log('❌ Validation: FAILED');
      result.errors.forEach(error => console.error(`  Error: ${error}`));
    }
    
    if (result.warnings.length > 0) {
      result.warnings.forEach(warning => console.warn(`  Warning: ${warning}`));
    }
    
    console.log('📊 Metadata:', result.metadata);
    console.groupEnd();
  }
}

/**
 * Comprehensive validation with logging for debugging
 */
export function validateAndLogRequest(payload: any, label?: string): ValidationResult {
  const result = validateLangServeRequest(payload);
  logValidationResult(result, label);
  return result;
}

/**
 * Test function to validate various request scenarios
 */
export function testRequestValidation(): void {
  if (process.env.NODE_ENV !== 'development') {
    return;
  }

  console.group('🧪 Request Validation Tests');

  const testCases = [
    {
      name: 'Valid direct request',
      payload: {
        mode: 'ask',
        message: 'Hello',
        wid: 'test-wb',
        sid: 'Sheet1',
        contexts: ['context1'],
        model: 'gpt-4'
      }
    },
    {
      name: 'Valid wrapped request',
      payload: {
        input: {
          mode: 'ask',
          message: 'Hello',
          wid: 'test-wb',
          sid: 'Sheet1',
          contexts: ['context1'],
          model: 'gpt-4'
        }
      }
    },
    {
      name: 'Missing required fields',
      payload: {
        mode: 'ask',
        message: 'Hello'
        // Missing wid, sid
      }
    },
    {
      name: 'Invalid contexts type',
      payload: {
        mode: 'ask',
        message: 'Hello',
        wid: 'test-wb',
        sid: 'Sheet1',
        contexts: 'not-an-array'
      }
    },
    {
      name: 'Null values',
      payload: {
        mode: 'ask',
        message: 'Hello',
        wid: 'test-wb',
        sid: 'Sheet1',
        contexts: null,
        model: null
      }
    }
  ];

  testCases.forEach(testCase => {
    console.log(`\n🔬 Testing: ${testCase.name}`);
    validateAndLogRequest(testCase.payload, testCase.name);
  });

  console.groupEnd();
} 
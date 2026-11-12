package com.example.kb_ai_backend.action;

/** 액션 처리 실패. code별 HTTP 상태 매핑은 컨트롤러에서 한다. */
public class ActionException extends RuntimeException {

    public enum Code {
        INVALID_REQUEST, NOT_FOUND, DENIED, EXPIRED, OTP_REQUIRED, OTP_MISMATCH, LOCKED,
        IDEMPOTENCY_CONFLICT, EXECUTION_FAILED
    }

    private final Code code;
    private final Integer remainingOtpAttempts;

    public ActionException(Code code, String message) {
        this(code, message, null);
    }

    public ActionException(Code code, String message, Integer remainingOtpAttempts) {
        super(message);
        this.code = code;
        this.remainingOtpAttempts = remainingOtpAttempts;
    }

    public Code code() { return code; }

    public Integer remainingOtpAttempts() { return remainingOtpAttempts; }
}

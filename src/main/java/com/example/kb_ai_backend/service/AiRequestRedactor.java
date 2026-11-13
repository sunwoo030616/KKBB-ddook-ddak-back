package com.example.kb_ai_backend.service;

import java.util.List;
import java.util.regex.Pattern;

/** Redacts identifiable formats at the outbound boundary; the original stays available to local slot parsing. */
final class AiRequestRedactor {
    private static final List<Pattern> SENSITIVE = List.of(
            Pattern.compile("(?i)(?<![\\w.+-])[\\w.+-]+@[a-z0-9-]+(?:\\.[a-z0-9-]+)+"),
            Pattern.compile("(?<![0-9])(?:\\+82[ .-]?(?:0[ .-]?)?|0)1[016789][ .-]?[0-9]{3,4}[ .-]?[0-9]{4}(?![0-9])"),
            Pattern.compile("(?<![0-9])[0-9]{6}[ -]?[1-8][0-9]{6}(?![0-9])"),
            Pattern.compile("(?<![0-9])(?:[0-9]{4}[ -]){3}[0-9]{4}(?![0-9])"),
            Pattern.compile("(?i)(?:계좌번호|카드번호|인증번호|비밀번호|otp)\\s*(?:[:=]|는|은)?\\s*[0-9](?:[0-9]|[- ](?=[0-9])){3,25}(?![0-9])")
    );

    private AiRequestRedactor() {}

    static String redact(String message) {
        for (Pattern pattern : SENSITIVE) {
            message = pattern.matcher(message).replaceAll("[민감정보]");
        }
        return message;
    }
}

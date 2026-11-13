package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.config.PresentationTokenConfig;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.context.annotation.Profile;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.net.InetAddress;
import java.net.UnknownHostException;
import java.time.Clock;
import java.time.Duration;
import java.util.List;
import java.util.UUID;

@RestController
@Profile("presentation")
public class PresentationTokenController {
    private final JwtEncoder encoder;
    private final Clock clock;

    public PresentationTokenController(JwtEncoder encoder, Clock clock) {
        this.encoder = encoder;
        this.clock = clock;
    }

    public record TokenResponse(String accessToken) {}

    @PostMapping("/api/presentation/token")
    public ResponseEntity<TokenResponse> issue(HttpServletRequest request) throws UnknownHostException {
        if (!InetAddress.getByName(request.getRemoteAddr()).isLoopbackAddress()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN);
        }
        var now = clock.instant();
        var claims = JwtClaimsSet.builder().issuer(PresentationTokenConfig.ISSUER)
                .audience(List.of(PresentationTokenConfig.AUDIENCE)).subject(UUID.randomUUID().toString())
                .issuedAt(now).expiresAt(now.plus(Duration.ofHours(8))).claim("scope", "actions:execute")
                .build();
        var headers = JwsHeader.with(MacAlgorithm.HS256).build();
        var token = encoder.encode(JwtEncoderParameters.from(headers, claims));
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(new TokenResponse(token.getTokenValue()));
    }
}

package com.example.kb_ai_backend.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * CORS 허용 도메인을 코드에 박아두지 않고 application.yml에서 주입받는다.
 * 개발(dev)/운영(prod) 프로필별로 다른 값을 넣을 수 있음.
 *
 * application.yml 예시:
 *
 * app:
 *   cors:
 *     allowed-origins:
 *       - https://your-frontend.com
 *       - https://staging.your-frontend.com
 *
 * (로컬 개발 시에는 application-dev.yml에 http://localhost:3000 등을 추가)
 */
@Configuration
public class CorsConfig implements WebMvcConfigurer {

    @Value("${app.cors.allowed-origins}")
    private String[] allowedOrigins;

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins(allowedOrigins)
                .allowedMethods("GET", "POST")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600);
    }
}
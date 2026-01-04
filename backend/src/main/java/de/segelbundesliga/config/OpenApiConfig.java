package de.segelbundesliga.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    @Value("${application.zitadel.issuer}")
    private String zitadelIssuer;

    @Bean
    public OpenAPI customOpenAPI() {
        final String oauth2SchemeName = "zitadel_oauth";
        final String bearerSchemeName = "bearer_token";

        return new OpenAPI()
                .info(new Info()
                        .title("Segel-Bundesliga API")
                        .version("1.0")
                        .description("API for Segel-Bundesliga tournament management\n\n" +
                                "**Quick Start:**\n" +
                                "1. Login to frontend: http://localhost:3000\n" +
                                "2. Open DevTools → Application → Local Storage\n" +
                                "3. Copy the access token\n" +
                                "4. Click 'Authorize' → Paste token into Bearer field"))
                .components(new Components()
                        .addSecuritySchemes(bearerSchemeName,
                                new SecurityScheme()
                                        .type(SecurityScheme.Type.HTTP)
                                        .scheme("bearer")
                                        .bearerFormat("JWT")
                                        .description("Paste JWT token from frontend login"))
                        .addSecuritySchemes(oauth2SchemeName,
                                new SecurityScheme()
                                        .type(SecurityScheme.Type.OAUTH2)
                                        .flows(new OAuthFlows()
                                                .authorizationCode(new OAuthFlow()
                                                        .authorizationUrl(zitadelIssuer + "/oauth/v2/authorize")
                                                        .tokenUrl(zitadelIssuer + "/oauth/v2/token")
                                                        .scopes(new Scopes()
                                                                .addString("openid", "OpenID Connect")
                                                                .addString("profile", "User profile")
                                                                .addString("email", "User email"))))))
                .addSecurityItem(new SecurityRequirement().addList(bearerSchemeName))
                .addSecurityItem(new SecurityRequirement().addList(oauth2SchemeName));
    }
}

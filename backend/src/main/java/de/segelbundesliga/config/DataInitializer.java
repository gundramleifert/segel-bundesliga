package de.segelbundesliga.config;

import de.segelbundesliga.domain.Page.FooterSection;
import de.segelbundesliga.domain.Page.Visibility;
import de.segelbundesliga.dto.PageDto;
import de.segelbundesliga.repository.PageRepository;
import de.segelbundesliga.service.PageService;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Initializes default CMS pages on application startup if they don't exist.
 * Runs after Liquibase migrations.
 */
@Component
@Order(100)
@RequiredArgsConstructor
public class DataInitializer implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(DataInitializer.class);

    private final PageRepository pageRepository;
    private final PageService pageService;

    @Override
    public void run(ApplicationArguments args) {
        log.info("Checking for default CMS pages...");

        List<DefaultPage> defaultPages = List.of(
                new DefaultPage(
                        "impressum",
                        "Impressum",
                        "Legal Notice",
                        "<h2>Impressum</h2><p>Angaben gemäß § 5 TMG</p>" +
                        "<p><strong>Herausgeber:</strong><br>" +
                        "Segel-Bundesliga<br>" +
                        "Musterstraße 1<br>" +
                        "12345 Musterstadt</p>" +
                        "<p><strong>Kontakt:</strong><br>" +
                        "E-Mail: info@segel-bundesliga.de<br>" +
                        "Telefon: +49 (0) 123 456789</p>",
                        "<h2>Legal Notice</h2><p>Information according to § 5 TMG</p>" +
                        "<p><strong>Publisher:</strong><br>" +
                        "Segel-Bundesliga<br>" +
                        "Sample Street 1<br>" +
                        "12345 Sample City</p>" +
                        "<p><strong>Contact:</strong><br>" +
                        "Email: info@segel-bundesliga.de<br>" +
                        "Phone: +49 (0) 123 456789</p>",
                        Visibility.PUBLIC,
                        100,
                        FooterSection.LEGAL
                ),
                new DefaultPage(
                        "datenschutz",
                        "Datenschutzerklärung",
                        "Privacy Policy",
                        "<h2>Datenschutzerklärung</h2>" +
                        "<h3>1. Datenschutz auf einen Blick</h3>" +
                        "<p>Diese Seite informiert Sie über den Umgang mit Ihren personenbezogenen Daten.</p>" +
                        "<h3>2. Datenerfassung auf dieser Website</h3>" +
                        "<p>Die Datenverarbeitung auf dieser Website erfolgt durch den Websitebetreiber.</p>" +
                        "<h3>3. Ihre Rechte</h3>" +
                        "<p>Sie haben jederzeit das Recht auf Auskunft, Berichtigung, Löschung oder Einschränkung " +
                        "der Verarbeitung Ihrer gespeicherten Daten.</p>",
                        "<h2>Privacy Policy</h2>" +
                        "<h3>1. Privacy at a Glance</h3>" +
                        "<p>This page informs you about the handling of your personal data.</p>" +
                        "<h3>2. Data Collection on this Website</h3>" +
                        "<p>Data processing on this website is carried out by the website operator.</p>" +
                        "<h3>3. Your Rights</h3>" +
                        "<p>You have the right to information, correction, deletion or restriction of " +
                        "processing of your stored data at any time.</p>",
                        Visibility.PUBLIC,
                        101,
                        FooterSection.LEGAL
                ),
                new DefaultPage(
                        "kontakt",
                        "Kontakt",
                        "Contact",
                        "<h2>Kontakt</h2>" +
                        "<p>Sie haben Fragen oder Anregungen? Wir freuen uns auf Ihre Nachricht!</p>" +
                        "<p><strong>E-Mail:</strong> info@segel-bundesliga.de<br>" +
                        "<strong>Telefon:</strong> +49 (0) 123 456789</p>" +
                        "<h3>Anschrift</h3>" +
                        "<p>Segel-Bundesliga<br>" +
                        "Musterstraße 1<br>" +
                        "12345 Musterstadt<br>" +
                        "Deutschland</p>",
                        "<h2>Contact</h2>" +
                        "<p>Do you have questions or suggestions? We look forward to hearing from you!</p>" +
                        "<p><strong>Email:</strong> info@segel-bundesliga.de<br>" +
                        "<strong>Phone:</strong> +49 (0) 123 456789</p>" +
                        "<h3>Address</h3>" +
                        "<p>Segel-Bundesliga<br>" +
                        "Sample Street 1<br>" +
                        "12345 Sample City<br>" +
                        "Germany</p>",
                        Visibility.PUBLIC,
                        102,
                        FooterSection.INFO
                ),
                new DefaultPage(
                        "agb",
                        "Allgemeine Geschäftsbedingungen",
                        "Terms and Conditions",
                        "<h2>Allgemeine Geschäftsbedingungen</h2>" +
                        "<h3>§ 1 Geltungsbereich</h3>" +
                        "<p>Diese Allgemeinen Geschäftsbedingungen gelten für alle Verträge zwischen dem Betreiber " +
                        "dieser Website und den Nutzern.</p>" +
                        "<h3>§ 2 Leistungen</h3>" +
                        "<p>Der Betreiber stellt auf dieser Website Informationen und Dienste für die " +
                        "Segel-Bundesliga zur Verfügung.</p>" +
                        "<h3>§ 3 Nutzungsrechte</h3>" +
                        "<p>Die Inhalte dieser Website sind urheberrechtlich geschützt.</p>",
                        "<h2>Terms and Conditions</h2>" +
                        "<h3>§ 1 Scope</h3>" +
                        "<p>These terms and conditions apply to all contracts between the operator of this " +
                        "website and the users.</p>" +
                        "<h3>§ 2 Services</h3>" +
                        "<p>The operator provides information and services for the Segel-Bundesliga on this website.</p>" +
                        "<h3>§ 3 Usage Rights</h3>" +
                        "<p>The content of this website is protected by copyright.</p>",
                        Visibility.PUBLIC,
                        103,
                        FooterSection.LEGAL
                ),
                new DefaultPage(
                        "ueber-uns",
                        "Über uns",
                        "About Us",
                        "<h2>Über die Segel-Bundesliga</h2>" +
                        "<p>Die Segel-Bundesliga ist der zentrale Wettbewerb für Segelvereine in Deutschland.</p>" +
                        "<h3>Unsere Mission</h3>" +
                        "<p>Wir fördern den Segelsport und schaffen spannende Wettkämpfe auf höchstem Niveau.</p>" +
                        "<h3>Geschichte</h3>" +
                        "<p>Seit ihrer Gründung hat sich die Segel-Bundesliga zu einem der wichtigsten " +
                        "Segelwettbewerbe Deutschlands entwickelt.</p>",
                        "<h2>About Segel-Bundesliga</h2>" +
                        "<p>The Segel-Bundesliga is the central competition for sailing clubs in Germany.</p>" +
                        "<h3>Our Mission</h3>" +
                        "<p>We promote sailing and create exciting competitions at the highest level.</p>" +
                        "<h3>History</h3>" +
                        "<p>Since its founding, the Segel-Bundesliga has become one of the most important " +
                        "sailing competitions in Germany.</p>",
                        Visibility.PUBLIC,
                        0,
                        null
                )
        );

        int created = 0;
        for (DefaultPage page : defaultPages) {
            if (!pageRepository.existsBySlug(page.slug)) {
                try {
                    PageDto.Create dto = new PageDto.Create();
                    dto.setTitle(page.title);
                    dto.setTitleEn(page.titleEn);
                    dto.setSlug(page.slug);
                    dto.setContent(page.content);
                    dto.setContentEn(page.contentEn);
                    dto.setVisibility(page.visibility);
                    dto.setSortOrder(page.sortOrder);
                    dto.setShowInMenu(false);
                    dto.setFooterSection(page.footerSection);

                    pageService.create(dto);
                    created++;
                    log.info("Created default page: {}", page.slug);
                } catch (Exception e) {
                    log.error("Failed to create default page: {}", page.slug, e);
                }
            } else {
                log.debug("Page already exists: {}", page.slug);
            }
        }

        if (created > 0) {
            log.info("Created {} default CMS pages", created);
        } else {
            log.info("All default CMS pages already exist");
        }
    }

    private record DefaultPage(
            String slug,
            String title,
            String titleEn,
            String content,
            String contentEn,
            Visibility visibility,
            int sortOrder,
            FooterSection footerSection
    ) {}
}

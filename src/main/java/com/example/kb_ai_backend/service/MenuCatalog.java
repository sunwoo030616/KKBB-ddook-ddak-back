package com.example.kb_ai_backend.service;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import java.io.IOException;
import java.security.MessageDigest;
import java.util.*;

/** Only active entries in the reviewed catalog may be selected. */
@Component
public class MenuCatalog {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Menu(String id, String name, String description,
                       @JsonProperty("select_when") List<String> selectWhen, List<String> aliases) {}
    private final Map<String, Menu> menus;
    private final String sha256;
    @org.springframework.beans.factory.annotation.Autowired
    public MenuCatalog(ObjectMapper mapper) throws IOException {
        this(mapper, catalogBytes());
    }
    private static byte[] catalogBytes() throws IOException {
        try (var input = new ClassPathResource("kb_starbanking_menu_structure_cleaned.json").getInputStream()) { return input.readAllBytes(); }
    }
    MenuCatalog(ObjectMapper mapper, byte[] bytes) throws IOException {
        try { sha256 = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); }
        catch (java.security.NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
        var root = mapper.readTree(bytes);
        if (!root.path("menus").isArray() || root.path("menus").isEmpty()) throw new IllegalStateException("Empty menu catalog");
        var entries = new LinkedHashMap<String, Menu>();
        var names = new HashSet<String>();
        for (var node : root.path("menus")) {
            var menu = mapper.treeToValue(node, Menu.class);
            if (menu.id() == null || !menu.id().matches("kb_menu_\\d{4,}")
                    || menu.name() == null || menu.name().isBlank()
                    || menu.description() == null || menu.description().isBlank()
                    || menu.selectWhen() == null || menu.selectWhen().isEmpty()
                    || menu.selectWhen().stream().anyMatch(s -> s == null || s.isBlank())
                    || node.path("excluded_from_retrieval").asBoolean(false)
                    || !Set.of("task", "product").contains(node.path("kind").asText())
                    || !names.add(menu.name().replaceAll("\\s+", "")) || entries.containsKey(menu.id()))
                throw new IllegalStateException("Invalid or duplicate menu catalog entry");
            entries.put(menu.id(), new Menu(menu.id(), menu.name(), menu.description(), List.copyOf(menu.selectWhen()),
                    menu.aliases() == null ? List.of() : List.copyOf(menu.aliases())));
        }
        if (!root.path("menu_count").isIntegralNumber() || root.path("menu_count").intValue() != entries.size())
            throw new IllegalStateException("Menu count mismatch");
        for (var node : root.path("excluded_menus"))
            if (entries.containsKey(node.path("id").asText())) throw new IllegalStateException("Excluded menu is active");
        menus = Collections.unmodifiableMap(entries);
    }
    public String sha256() { return sha256; }
    public Collection<Menu> all() { return menus.values(); }
    public Menu find(String id) { return menus.get(id); }
}

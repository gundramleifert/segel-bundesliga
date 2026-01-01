package gundramleifert.pairing_list.configs;


import com.fasterxml.jackson.annotation.JsonProperty;
import gundramleifert.pairing_list.Optimizer;
import gundramleifert.pairing_list.Yaml;

import java.io.File;
import java.io.IOException;
import java.net.URISyntaxException;
import java.net.URL;
import java.util.List;

public class OptimizationConfig {

    public static OptimizationConfig readYaml(String string) throws IOException, URISyntaxException {
        if (new File(string).exists()) {
            return readYaml(new File(string));
        }
        URL resource = Optimizer.class.getClassLoader().getResource(string);
        if (resource == null) {
            throw new IllegalArgumentException("file not found in resources an on disc");
        }
        File file = new File(resource.toURI());
        return readYaml(file);

    }

    public static OptimizationConfig readYaml(final File file) throws IOException {
        OptimizationConfig properties = Yaml.dftMapper().readValue(file, OptimizationConfig.class);
        return properties;
    }

    public static void writeYaml(final File file, OptimizationConfig properties) throws IOException {
        Yaml.dftMapper().writeValue(file, properties);
    }

    @JsonProperty
    public OptBoatConfig optBoatUsage;
    @JsonProperty
    public OptMatchMatrixConfig optMatchMatrix;

    @JsonProperty
    public int seed;

}

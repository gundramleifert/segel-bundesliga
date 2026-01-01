package gundramleifert.pairing_list;

import com.fasterxml.jackson.annotation.JsonAutoDetect;
import com.fasterxml.jackson.annotation.PropertyAccessor;
import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.deser.std.StdDeserializer;
import com.fasterxml.jackson.databind.module.SimpleModule;
import com.fasterxml.jackson.databind.node.IntNode;
import com.fasterxml.jackson.databind.ser.std.StdSerializer;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import gundramleifert.pairing_list.types.Race;

import java.io.IOException;

public class Yaml {
    public static ObjectMapper dftMapper() {
        SimpleModule module = new SimpleModule();
        module.addSerializer(new RaceSerializer());
        module.addDeserializer(Race.class,new RaceDeserializer());
        final ObjectMapper mapper = new ObjectMapper(new YAMLFactory()); // jackson databind
        mapper.setVisibility(PropertyAccessor.ALL, JsonAutoDetect.Visibility.NONE);
        mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
        mapper.registerModule(module);
        return mapper;
    }

    private static class RaceDeserializer extends StdDeserializer<Race> {

        public RaceDeserializer() {
            this(null);
        }

        public RaceDeserializer(Class<?> vc) {
            super(vc);
        }

        @Override
        public Race deserialize(JsonParser jp, DeserializationContext ctxt)
                throws IOException, JsonProcessingException {
            JsonNode node = jp.getCodec().readTree(jp);
            String[] teamsAsStr = node.asText().trim().split(",");
            byte[] teams = new byte[teamsAsStr.length];
            for (int i = 0; i < teams.length; i++) {
                teams[i]=Byte.parseByte(teamsAsStr[i]);
            }

            return new Race(teams);
        }
    }
    private static class RaceSerializer extends StdSerializer<Race>{
        public RaceSerializer(){
            this(Race.class);
        }

        public RaceSerializer(Class<Race> t) {
            super(t);
        }

        @Override
        public void serialize(Race race, JsonGenerator jsonGenerator, SerializerProvider serializerProvider) throws IOException {
            StringBuilder sb = new StringBuilder();
            byte[] bytes = race.teams;
            sb.append(bytes[0]);
            int[] res = new int[bytes.length];
            for (int i = 1; i < bytes.length; i++) {
                sb.append(',').append(bytes[i]);
            }
            jsonGenerator.writeString(sb.toString());
        }
    }

}
